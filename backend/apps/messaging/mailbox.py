"""Reading the study mailbox into Communications (PI decision, 2026-10-12).

Every EMAIL_INBOX_POLL_MINUTES a Celery beat task reads new mail in the study's email account over IMAP:

- the inbox (EMAIL_INBOX_FOLDER): an email from an address on a Main-400 case or KII record, or one answering an email
  the portal sent (In-Reply-To / References), is copied in as an InboundMessage on that case or record and waits for a
  person. A bounce for an email the portal sent marks it "not delivered".
- the sent folder (EMAIL_SENT_FOLDER): an email the team wrote in Gmail itself to an address on a case or record is
  copied in as a sent message, so the conversation shows both sides. Copies of the portal's own emails are skipped.

Everything else is never copied: for an email that matches nothing only its headers are looked at, and nothing is
kept. The mailbox is opened read-only (EXAMINE) and read with BODY.PEEK, so nothing in it is marked read, moved or
changed. How far each folder has been read is kept in MailboxCursor; the first read looks back
EMAIL_INBOX_BACKFILL_DAYS, so replies to emails sent before this existed are found too.
"""

import email
import email.policy
import html
import imaplib
import logging
import re
from datetime import timedelta
from datetime import timezone as dt_timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from .hashing import email_hash, mask_email
from .matching import find_by_email, known_email_addresses
from .models import (
    InboundMessage,
    MailboxCursor,
    MessageChannel,
    MessageProvider,
    MessagePurpose,
    ProviderMessage,
    ProviderStatus,
    ReplyKind,
)
from .outbound import scrub

logger = logging.getLogger(__name__)

HEADER_FIELDS = "FROM TO CC MESSAGE-ID IN-REPLY-TO REFERENCES DATE SUBJECT X-FAILED-RECIPIENTS AUTO-SUBMITTED"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BOUNCE_SENDERS = ("mailer-daemon@", "postmaster@")
MAX_BODY = 20000
UID_RE = re.compile(rb"UID (\d+)")


def configured() -> bool:
    return bool((settings.EMAIL_IMAP_HOST or "").strip() and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)


def _connect():
    conn = imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST.strip(), settings.EMAIL_IMAP_PORT, timeout=60)
    conn.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    return conn


def _quote(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(when) -> str:
    return f"{when.day:02d}-{MONTHS[when.month - 1]}-{when.year}"


def _fetched(data) -> list[tuple[int, bytes]]:
    """(uid, payload) pairs from an IMAP FETCH answer."""
    out = []
    for item in data or []:
        if isinstance(item, tuple) and len(item) >= 2:
            found = UID_RE.search(item[0])
            if found:
                out.append((int(found.group(1)), item[1]))
    return out


def _addresses(value) -> list[str]:
    return [a.strip().lower() for _, a in getaddresses([str(value or "")]) if "@" in (a or "")]


def _ids(value) -> list[str]:
    return re.findall(r"<[^<>\s]+>", str(value or ""))


def _date(value):
    """The email's Date header as an aware time. "-0000" (what Django's own emails carry: time zone not stated) parses
    to a naive time, read as UTC. Until 2026-10-12 21:00 this used timezone.utc, which Django 5 no longer has: every
    such email raised, so the portal's own earlier invitations came in from the sent folder dated at sync time, and an
    inbox reply carrying that form of date was skipped."""
    try:
        when = parsedate_to_datetime(str(value))
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    return when if timezone.is_aware(when) else when.replace(tzinfo=dt_timezone.utc)


def text_of(message) -> tuple[str, bool]:
    """(the readable text, has attachments). Plain text preferred; HTML is reduced to its text."""
    attachments = any(part.get_content_disposition() == "attachment" for part in message.walk())
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return "", attachments
    try:
        text = part.get_content()
    except (LookupError, UnicodeDecodeError):
        text = part.get_payload(decode=True).decode("utf-8", "replace") if part.get_payload(decode=True) else ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = "\n".join(" ".join(line.split()) for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_BODY], attachments


def _portal_message(ids: list[str]):
    if not ids:
        return None
    return ProviderMessage.objects.filter(channel=MessageChannel.EMAIL, provider_sid__in=ids).order_by("-created_at").first()


class _Folder:
    def __init__(self, conn, folder: str, now):
        self.conn, self.folder, self.now = conn, folder, now

    def open(self) -> int:
        typ, _ = self.conn.select(_quote(self.folder), readonly=True)
        if typ != "OK":
            raise imaplib.IMAP4.error(f"Could not open the folder {self.folder}")
        _, data = self.conn.response("UIDVALIDITY")
        value = (data or [b""])[0] or b""
        value = value.decode() if isinstance(value, bytes) else str(value)
        return int(value) if value.strip().isdigit() else 0

    def new_uids(self, cursor: MailboxCursor, validity: int) -> list[int]:
        if cursor.uidvalidity != validity or not cursor.last_uid:
            since = self.now - timedelta(days=settings.EMAIL_INBOX_BACKFILL_DAYS)
            typ, data = self.conn.uid("SEARCH", None, f"SINCE {_imap_date(since)}")
            floor = 0
        else:
            typ, data = self.conn.uid("SEARCH", None, f"UID {cursor.last_uid + 1}:*")
            floor = cursor.last_uid
        uids = sorted(int(u) for u in b" ".join(d for d in (data or []) if d).split() if u.isdigit())
        return [u for u in uids if u > floor][: settings.EMAIL_INBOX_MAX_PER_RUN]

    def headers(self, uids: list[int]) -> dict[int, object]:
        if not uids:
            return {}
        _, data = self.conn.uid("FETCH", ",".join(map(str, uids)), f"(UID BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})])")
        return {uid: email.message_from_bytes(raw, policy=email.policy.default) for uid, raw in _fetched(data)}

    def full(self, uid: int):
        _, data = self.conn.uid("FETCH", str(uid), "(UID BODY.PEEK[])")
        for _, raw in _fetched(data):
            return email.message_from_bytes(raw, policy=email.policy.default)
        return None


def _bounce(head, folder: _Folder, uid: int) -> bool:
    """A delivery failure for an email the portal sent: mark that email not delivered. Never stored itself."""
    failed = _addresses(head.get("X-Failed-Recipients"))
    reason = "The address could not receive email."
    if not failed:
        message = folder.full(uid)
        if message is None:
            return False
        for part in message.walk():
            if part.get_content_type() == "message/delivery-status":
                text = part.as_string()
                failed = [a.split(";")[-1].strip().lower() for a in re.findall(r"(?im)^Final-Recipient:\s*(.+)$", text)]
                found = re.search(r"(?im)^Diagnostic-Code:\s*(.+)$", text)
                if found:
                    reason = found.group(1).strip()[:280]
    hit = 0
    for address in failed:
        sent = (ProviderMessage.objects.filter(channel=MessageChannel.EMAIL, provider=MessageProvider.SMTP,
                                               to_hash=email_hash(address), created_at__gte=folder.now - timedelta(days=14))
                .exclude(status=ProviderStatus.UNDELIVERED).order_by("-created_at").first())
        if sent:
            sent.status, sent.error_message = ProviderStatus.UNDELIVERED, reason
            sent.save(update_fields=["status", "error_message", "updated_at"])
            hit += 1
    return bool(hit)


def _store_inbound(head, folder: _Folder, uid: int, validity: int, known: set[str]) -> bool:
    sender = parseaddr(str(head.get("From", "")))[1].strip().lower()
    if sender.startswith(BOUNCE_SENDERS):
        return _bounce(head, folder, uid)
    answered = _portal_message(_ids(head.get("In-Reply-To")) + _ids(head.get("References")))
    if answered is None and sender not in known:
        return False  # not from anyone on a case or record: nothing is read or kept
    message_id = (_ids(head.get("Message-ID")) or [f"<imap-{validity}-{uid}@{folder.folder}>"])[0]
    if InboundMessage.objects.filter(provider_sid=message_id).exists():
        return False
    if answered is not None:
        case, record = answered.sample_case, answered.kii_record
    else:
        case, record = find_by_email(sender)
    if case is None and record is None:
        return False
    full = folder.full(uid)
    if full is None:
        return False
    body, attachments = text_of(full)
    # An out-of-office answer is kept (it says when they are back) but needs nobody to act on it.
    automatic = str(head.get("Auto-Submitted", "no")).lower() not in ("", "no")
    try:
        InboundMessage.objects.create(
            channel=MessageChannel.EMAIL, provider_sid=message_id[:255], sample_case=case, kii_record=record,
            number_hash=email_hash(sender), from_masked=mask_email(sender), subject=scrub(str(head.get("Subject", "")))[:300],
            body=scrub(body), has_attachments=attachments, sent_at=_date(head.get("Date")), kind=ReplyKind.OTHER,
            needs_person=not automatic,
        )
    except IntegrityError:
        return False
    return True


def _store_sent(head, folder: _Folder, uid: int, validity: int, known: set[str]) -> bool:
    message_id = (_ids(head.get("Message-ID")) or [f"<imap-{validity}-{uid}@{folder.folder}>"])[0]
    if ProviderMessage.objects.filter(provider_sid=message_id).exists():
        return False  # the portal's own email, or already copied
    recipients = [a for a in _addresses(head.get("To")) + _addresses(head.get("Cc")) if a in known]
    if not recipients:
        return False
    to = recipients[0]
    answered = _portal_inbound(_ids(head.get("In-Reply-To")) + _ids(head.get("References")))
    case, record = (answered.sample_case, answered.kii_record) if answered else find_by_email(to)
    if case is None and record is None:
        return False
    full = folder.full(uid)
    if full is None:
        return False
    body, _ = text_of(full)
    try:
        sent = ProviderMessage.objects.create(
            channel=MessageChannel.EMAIL, purpose=MessagePurpose.MESSAGE, provider=MessageProvider.GMAIL_SENT,
            provider_sid=message_id[:255], to_masked=mask_email(to), to_hash=email_hash(to),
            subject=scrub(str(head.get("Subject", "")))[:300], body=scrub(body), status=ProviderStatus.SENT, sample_case=case,
            kii_record=record,
        )
    except IntegrityError:
        return False
    when = _date(head.get("Date"))
    if when:
        ProviderMessage.objects.filter(pk=sent.pk).update(created_at=when)
    # Answering in Gmail deals with what they wrote.
    InboundMessage.objects.filter(channel=MessageChannel.EMAIL, number_hash=email_hash(to), needs_person=True,
                                  received_at__lte=when or folder.now).update(needs_person=False, handled_at=folder.now)
    return True


def _portal_inbound(ids: list[str]):
    if not ids:
        return None
    return InboundMessage.objects.filter(channel=MessageChannel.EMAIL, provider_sid__in=ids).first()


def sync_mailbox(*, connect=None, now=None) -> dict:
    """Read new mail in the inbox and sent folder. Returns what was copied in."""
    if not configured():
        return {"skipped": "EMAIL_IMAP_HOST is not set"}
    now = now or timezone.now()
    known = known_email_addresses()
    folders = [(settings.EMAIL_INBOX_FOLDER, _store_inbound)]
    if (settings.EMAIL_SENT_FOLDER or "").strip():
        folders.append((settings.EMAIL_SENT_FOLDER.strip(), _store_sent))
    result = {}
    try:
        conn = (connect or _connect)()
    except (imaplib.IMAP4.error, OSError) as exc:
        MailboxCursor.objects.update_or_create(folder=settings.EMAIL_INBOX_FOLDER,
                                               defaults={"last_error": f"Could not sign in to the mailbox: {exc}"[:300]})
        logger.warning("Mailbox sign-in failed: %s", exc)
        return {"error": str(exc)}
    try:
        for name, store in folders:
            cursor, _ = MailboxCursor.objects.get_or_create(folder=name)
            stored = 0
            try:
                folder = _Folder(conn, name, now)
                validity = folder.open()
                uids = folder.new_uids(cursor, validity)
                if cursor.uidvalidity != validity:  # the folder was rebuilt: its old UIDs mean nothing now
                    cursor.uidvalidity, cursor.last_uid = validity, 0
                heads = folder.headers(uids)
                for uid in uids:
                    head = heads.get(uid)
                    try:
                        if head is not None and store(head, folder, uid, validity, known):
                            stored += 1
                    except Exception:  # noqa: BLE001 -- one unreadable email must not stop the rest
                        logger.exception("Email %s in %s could not be read", uid, name)
                    cursor.last_uid = max(cursor.last_uid, uid)
                cursor.last_synced_at, cursor.last_error = now, ""
            except (imaplib.IMAP4.error, OSError) as exc:
                cursor.last_error = f"{exc}"[:300]
                logger.warning("Mailbox folder %s not read: %s", name, exc)
            cursor.save()
            result[name] = stored
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 -- the connection is being dropped anyway
            pass
    return result
