"""Sending one message -- SMS or WhatsApp through Twilio (2026-10-07), email through the study's mail server
(2026-10-12) -- and recording what happened to it.

The single place invitations (Main-400 and KII, one at a time and in batches), automatic reminders, introductions and
messages written in Communications go through, so the daily caps, the "is this channel set up" check and the
ProviderMessage record are applied the same way to all of them. Callers check their own rules first: the invitation's
own link, is_invitable(), the reminder sequence.

What was sent is kept on the ProviderMessage so Communications can show it, with the personal link and manual code
replaced (redact()): a link works like a password, and the portal otherwise keeps only its hash.
"""

import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action

from . import twilio_client as tw
from .hashing import email_hash, mask_email, number_hash
from .models import (
    MessageChannel,
    MessageProvider,
    MessagePurpose,
    MessageStatus,
    ProviderMessage,
    ProviderStatus,
)

LINK_PLACEHOLDER = "[personal link]"
CODE_PLACEHOLDER = "[code]"
# Any invitation link (Main-400 /i/..., KII /ki/...) and a manual code after the word "code", wherever they appear:
# an email reply quotes the invitation it answers, and the team's own Gmail copies hold the link in full.
INVITATION_LINK = re.compile(r"https?://\S+?/k?i/[A-Za-z0-9_-]{20,}")
MANUAL_CODE = re.compile(r"(?i)(\bcode\s*:?\s*)([A-Z0-9]{8})\b")

TWILIO_STATUS = {
    "accepted": ProviderStatus.QUEUED, "scheduled": ProviderStatus.QUEUED, "queued": ProviderStatus.QUEUED,
    "sending": ProviderStatus.QUEUED, "sent": ProviderStatus.SENT, "delivered": ProviderStatus.DELIVERED,
    "read": ProviderStatus.READ, "undelivered": ProviderStatus.UNDELIVERED, "failed": ProviderStatus.FAILED,
    "canceled": ProviderStatus.FAILED,
}
PROGRESS = [ProviderStatus.QUEUED, ProviderStatus.SENT, ProviderStatus.DELIVERED, ProviderStatus.READ]
NOT_DELIVERED = [ProviderStatus.UNDELIVERED, ProviderStatus.FAILED]


class OutboundError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def daily_max(channel: str) -> int:
    """SMS: TWILIO_SMS_DAILY_MAX messages a day. WhatsApp: the smaller of the study's own ceiling
    (TWILIO_WHATSAPP_DAILY_MAX) and Meta's current limit for the number, read from Twilio (2026-10-14) -- Meta raises
    it by itself (250, then 2,000, 10,000...) and the portal follows."""
    if channel == MessageChannel.SMS:
        return max(0, int(getattr(settings, "TWILIO_SMS_DAILY_MAX", 0)))
    ceiling = max(0, int(getattr(settings, "TWILIO_WHATSAPP_DAILY_MAX", 0)))
    meta = tw.meta_messaging_limit()
    return ceiling if meta is None else min(ceiling, meta)


def sent_today(channel: str) -> int:
    """SMS: messages sent since midnight. WhatsApp: what Meta counts -- different people sent a template (an
    introduction, reminder or invitation sent first) in the last 24 hours. Free-text replies inside a conversation the
    person started, such as the link after a YES, are not counted (2026-10-14)."""
    if channel == MessageChannel.WHATSAPP:
        since = timezone.now() - timedelta(hours=24)
        return (ProviderMessage.objects.filter(channel=channel, is_template=True, created_at__gte=since)
                .values("to_hash").distinct().count())
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return ProviderMessage.objects.filter(channel=channel, created_at__gte=start).count()


def _already_counted(number: str) -> bool:
    """A template to someone already sent one in the last 24 hours does not use up Meta's limit again."""
    since = timezone.now() - timedelta(hours=24)
    return ProviderMessage.objects.filter(channel=MessageChannel.WHATSAPP, is_template=True, created_at__gte=since,
                                          to_hash=number_hash(number)).exists()


def left_today(channel: str) -> int:
    return max(0, daily_max(channel) - sent_today(channel))


def configured(channel: str, *, kii: bool = False) -> bool:
    return tw.sms_configured() if channel == MessageChannel.SMS else tw.whatsapp_configured(kii=kii)


def redact(text: str, *, link: str = "", code: str = "") -> str:
    """The text as it may be kept: the personal link and the manual code replaced. Longest first, so a code that
    happens to appear inside the link can't leave part of the link behind."""
    text = text or ""
    for secret, placeholder in sorted(((link, LINK_PLACEHOLDER), (code, CODE_PLACEHOLDER)), key=lambda p: -len(p[0] or "")):
        if secret and len(secret) >= 4:
            text = text.replace(secret, placeholder)
    return scrub(text)


def scrub(text: str) -> str:
    """Takes out every invitation link and quoted manual code, known or not."""
    text = INVITATION_LINK.sub(LINK_PLACEHOLDER, text or "")
    return MANUAL_CODE.sub(lambda m: m.group(1) + CODE_PLACEHOLDER, text)


def _template_label(purpose: str) -> str:
    return f"[Approved WhatsApp template: {MessagePurpose(purpose).label.lower()}]"


def send(*, channel: str, number: str, purpose: str, sms_body: str = "", wa_content: str = "", wa_variables=None,
         wa_text: str = "", user=None, record_text: str = "", redact_link: str = "", redact_code: str = "",
         **links) -> ProviderMessage:
    """Sends one message and records it. `links` names what it belongs to: sample_case or kii_record, and
    invitation_token, kii_invitation_token or message_log. WhatsApp is an approved template (`wa_content`) unless
    `wa_text` is given: a free-text reply inside a conversation the person started. `record_text` is what to show for
    a template (the portal's own copy of its wording); `redact_link` / `redact_code` are taken out of what is kept.
    Raises OutboundError with words a coordinator can act on."""
    label = "SMS" if channel == MessageChannel.SMS else "WhatsApp"
    if channel == MessageChannel.SMS and not tw.sms_configured():
        raise OutboundError("sms_not_configured", "SMS isn't set up on the server yet (deploy/configure-twilio.sh).", 503)
    if channel == MessageChannel.WHATSAPP and not ((wa_content or wa_text) and tw.credentials_set() and settings.TWILIO_WHATSAPP_FROM.strip()):
        raise OutboundError("whatsapp_not_configured",
                            "WhatsApp sending isn't set up yet: it needs the Meta-approved sender and template (deploy/configure-twilio.sh).", 503)
    if channel == MessageChannel.WHATSAPP and wa_content and not wa_text:
        waiting = tw.content_waiting(wa_content)
        if waiting:  # Twilio would accept it and fail it later (63016), so it would look sent (2026-10-13)
            raise OutboundError("whatsapp_template_not_approved",
                                f"WhatsApp can't be used for this yet: Meta hasn't approved its template (it is {waiting}). "
                                "Send by email or SMS for now.", 409)
    if not number:
        raise OutboundError("no_mobile", "No mobile number is on file (a landline can't receive SMS or WhatsApp). Add one under contact details.")
    template = channel == MessageChannel.WHATSAPP and not wa_text
    capped = channel == MessageChannel.SMS or (template and not _already_counted(number))
    if capped and left_today(channel) < 1:
        raise OutboundError("daily_limit_reached", f"Today's limit of {daily_max(channel)} {label} messages has been reached. Try again tomorrow.", 409)
    try:
        if channel == MessageChannel.SMS:
            result = tw.send_sms(number, sms_body)
        elif wa_text:
            result = tw.send_whatsapp_text(number, wa_text)
        else:
            result = tw.send_whatsapp(number, wa_content, wa_variables)
    except tw.TwilioError as exc:
        raise OutboundError("twilio_refused", f"The {label} message was not sent: {exc}", 502) from exc
    segments = result.get("num_segments")
    if channel == MessageChannel.SMS:
        shown = tw.with_opt_out(sms_body)
    else:
        shown = wa_text or record_text or _template_label(purpose)
    return ProviderMessage.objects.create(
        channel=channel, purpose=purpose, provider=MessageProvider.TWILIO, provider_sid=result.get("sid") or None,
        to_masked=tw.mask(number), to_hash=number_hash(number), body=redact(shown, link=redact_link, code=redact_code),
        status=TWILIO_STATUS.get(str(result.get("status", "")).lower(), ProviderStatus.QUEUED),
        segments=int(segments) if str(segments or "").isdigit() else None, sent_by=user, is_template=template, **links,
    )


def email_configured() -> bool:
    from apps.kobo.submission_copies import email_is_configured

    return email_is_configured()


def split_text(text: str, limit: int | None = None) -> list[str]:
    """A written message cut into parts that each fit one WhatsApp or SMS body (2026-10-17): at paragraph breaks, then
    sentence breaks, then spaces, never inside a word unless a single word is longer than a part. The writer's
    paragraphs are kept. Each part of a message that needs more than one is numbered "(1/3) "; a message that fits is
    returned as it is."""
    limit = limit or settings.COMMUNICATION_TEXT_PART_MAX
    text = (text or "").strip()
    if len(text) <= limit:
        return [text]
    room = limit - len("(99/99) ")

    def cut(block: str, separators: list[str]) -> list[str]:
        if len(block) <= room:
            return [block]
        if not separators:
            return [block[i:i + room] for i in range(0, len(block), room)]
        out = []
        for piece in re.split(separators[0], block):
            out.extend(cut(piece.strip(), separators[1:]))
        return [p for p in out if p]

    # (unit, starts a paragraph) in reading order
    units = []
    for paragraph in re.split(r"\n\s*\n", text):
        for i, unit in enumerate(cut(paragraph.strip(), [r"(?<=[.!?:;])\s+", r"\s+"])):
            units.append((unit, i == 0))
    parts, current = [], ""
    for unit, new_paragraph in units:
        candidate = f"{current}{chr(10) * 2 if new_paragraph else ' '}{unit}" if current else unit
        if len(candidate) <= room:
            current = candidate
        else:
            parts.append(current)
            current = unit
    if current:
        parts.append(current)
    return [f"({i}/{len(parts)}) {p}" for i, p in enumerate(parts, 1)]


def send_text(*, channel: str, number: str, purpose: str, text: str, user=None, **links) -> list[ProviderMessage]:
    """A written WhatsApp or SMS message, sent as one or more numbered parts in order (split_text). If a part fails
    after others went, the error says which parts went, so nothing is half-sent without the writer knowing."""
    parts = split_text(text)
    sent: list[ProviderMessage] = []
    for number_in_order, part in enumerate(parts, 1):
        try:
            sent.append(send(channel=channel, number=number, purpose=purpose, user=user,
                             wa_text=part if channel == MessageChannel.WHATSAPP else "",
                             sms_body=part if channel == MessageChannel.SMS else "", **links))
        except OutboundError as exc:
            if not sent:
                raise
            went = "part 1" if len(sent) == 1 else f"parts 1-{len(sent)}"
            raise OutboundError(exc.code, f"Only {went} of {len(parts)} went. Part {number_in_order} was not sent ({exc}): "
                                          f"send the rest again as a new message.", exc.status) from exc
    return sent


def send_email(*, to: str, subject: str, body: str, purpose: str, user=None, in_reply_to: str = "",
               redact_link: str = "", redact_code: str = "", **links) -> ProviderMessage:
    """One email from the study address, recorded like an SMS or WhatsApp message. It carries its own Message-ID, so a
    reply (In-Reply-To) or a bounce can be matched back to it by apps/messaging/mailbox.py. A refusal by the mail
    server is recorded as FAILED and then raised as it was, so callers that already catch it behave as before."""
    from django.core.mail import EmailMessage
    from django.core.mail.message import make_msgid

    if not email_configured():
        raise OutboundError("email_not_configured", "Email isn't set up on the server yet.", 503)
    to = (to or "").strip()
    if not to:
        raise OutboundError("no_email", "No email address is on file. Add one under contact details.")
    message_id = make_msgid(domain=(settings.APP_DOMAIN or "localhost").split(":")[0])
    headers = {"Message-ID": message_id}
    if in_reply_to:
        headers.update({"In-Reply-To": in_reply_to, "References": in_reply_to})
    record = ProviderMessage(
        channel=MessageChannel.EMAIL, purpose=purpose, provider=MessageProvider.SMTP, provider_sid=message_id,
        to_masked=mask_email(to), to_hash=email_hash(to), subject=redact(subject, link=redact_link, code=redact_code)[:300],
        body=redact(body, link=redact_link, code=redact_code), sent_by=user, **links,
    )
    try:
        EmailMessage(
            subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[to],
            reply_to=[settings.STUDY_REPLY_TO_EMAIL] if settings.STUDY_REPLY_TO_EMAIL else None, headers=headers,
        ).send(fail_silently=False)
    except Exception as exc:
        record.status, record.error_message = ProviderStatus.FAILED, f"The mail server refused it: {exc}"[:300]
        record.save()
        raise
    record.status = ProviderStatus.SENT
    record.save()
    return record


def record_status(params: dict) -> bool:
    """Applies one Twilio status callback. Delivery reports can arrive out of order ("sent" after "delivered"), so a
    message only moves forward; not delivered is final. A reminder Twilio could not deliver is marked FAILED on its
    MessageLog, which puts it back on Follow-ups for a person rather than counting toward Nonresponse."""
    message = ProviderMessage.objects.select_related("message_log").filter(provider_sid=params.get("MessageSid") or None).first()
    if message is None:
        return False
    new = TWILIO_STATUS.get(str(params.get("MessageStatus", "")).lower())
    if new is None or message.status in NOT_DELIVERED or new == message.status:
        return True
    if new not in NOT_DELIVERED and PROGRESS.index(new) < PROGRESS.index(message.status):
        return True
    message.status = new
    message.error_code = str(params.get("ErrorCode") or "")[:16]
    message.error_message = str(params.get("ErrorMessage") or "")[:300]
    message.save(update_fields=["status", "error_code", "error_message", "updated_at"])
    if new in NOT_DELIVERED:
        if message.purpose == MessagePurpose.INTRODUCTION:
            from .outreach import intro_not_delivered

            intro_not_delivered(message)
        if message.message_log_id:
            message.message_log.status = MessageStatus.FAILED
            message.message_log.save(update_fields=["status"])
        log_action("twilio.message_failed", message.sample_case or message.kii_record or message, {
            "channel": message.channel, "purpose": message.purpose, "recipient": message.to_masked,
            "error_code": message.error_code, "provider_message": message.pk,
        })
    return True
