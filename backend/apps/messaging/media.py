"""What people send the study on WhatsApp besides text (2026-10-14): voice notes, pictures, shared contacts, files.

Until 2026-10-14 the incoming-message webhook kept only the text, so a message that was only a voice note or a contact
card arrived empty -- on the first fresh-start day an agricultural college shared "this person" to contact, and nobody
could see who. Now each attachment is listed from Twilio (Messages/{sid}/Media), copied into PRIVATE_DATA_ROOT (never a
web-served directory) and opened only through Communications by people who may see that conversation. A shared
contact (vCard) is also read, so its name and number show as text. Size is capped by WHATSAPP_MEDIA_MAX_MB.

Also here: spotting a reply that is the person's own invitation code -- the invitation says "Prefer to answer by phone?
Reply and quote code ABCD2345" -- so it is flagged "Wants to answer by phone" instead of looking like a stray word.
"""

import logging
import mimetypes
import os
import re

import requests
from django.conf import settings

from . import twilio_client as tw
from .models import AttachmentKind, InboundAttachment

logger = logging.getLogger(__name__)

API = "https://api.twilio.com"
FOLDER = "whatsapp_media"
CODE_WORD = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{8})(?![A-Za-z0-9])")


def kind_of(content_type: str) -> str:
    ct = (content_type or "").lower()
    if ct in ("text/vcard", "text/x-vcard", "text/directory"):
        return AttachmentKind.CONTACT
    if ct.startswith("audio/"):
        return AttachmentKind.VOICE
    if ct.startswith("image/"):
        return AttachmentKind.IMAGE
    if ct.startswith("video/"):
        return AttachmentKind.VIDEO
    if ct.startswith("application/") or ct.startswith("text/"):
        return AttachmentKind.DOCUMENT
    return AttachmentKind.OTHER


def read_vcard(text: str) -> str:
    """"Name, number[, number], email" from a vCard: what a person needs to follow up a shared contact."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text or "")
    name, numbers, emails = "", [], []
    for line in unfolded.splitlines():
        key, _, value = line.partition(":")
        field = key.split(";")[0].upper()
        value = value.strip()
        if field == "FN" and value:
            name = value
        elif field == "N" and value and not name:
            name = " ".join(part for part in reversed(value.split(";")[:2]) if part).strip()
        elif field == "TEL" and value:
            numbers.append(value)
        elif field == "EMAIL" and value:
            emails.append(value)
    return ", ".join([name or "(no name)", *dict.fromkeys(numbers), *dict.fromkeys(emails)])[:500]


def _max_bytes() -> int:
    return int(float(getattr(settings, "WHATSAPP_MEDIA_MAX_MB", 16)) * 1024 * 1024)


def fetch_attachments(message, *, get=None) -> int:
    """List the message's media on Twilio and keep a private copy of each. Safe to run again: a message whose
    attachments are already stored is left alone. Returns how many were stored."""
    if message.attachments.exists() or not tw.credentials_set():
        return 0
    get = get or requests.get
    account, token = tw._account()
    listing = get(f"{API}/2010-04-01/Accounts/{account}/Messages/{message.provider_sid}/Media.json", auth=(account, token), timeout=20)
    if listing.status_code != 200:
        logger.warning("Media list for %s: HTTP %s", message.provider_sid, listing.status_code)
        return 0
    stored = 0
    for media in (listing.json() or {}).get("media_list", []):
        content_type = media.get("content_type", "")
        attachment = InboundAttachment(message=message, kind=kind_of(content_type), content_type=content_type[:100])
        try:
            response = get(API + media["uri"].removesuffix(".json"), auth=(account, token), timeout=60)
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            data = response.content
            if len(data) > _max_bytes():
                raise ValueError(f"larger than {getattr(settings, 'WHATSAPP_MEDIA_MAX_MB', 16)} MB")
            ext = mimetypes.guess_extension(content_type.split(";")[0]) or ".bin"
            rel = os.path.join(FOLDER, str(message.pk), f"{media.get('sid', 'media')}{ext}")
            path = os.path.join(settings.PRIVATE_DATA_ROOT, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
            attachment.file_ref, attachment.size = rel, len(data)
            if attachment.kind == AttachmentKind.CONTACT:
                attachment.contact_text = read_vcard(data.decode("utf-8", "replace"))
            stored += 1
        except (requests.RequestException, ValueError, KeyError, OSError) as exc:
            attachment.error = f"Could not be copied from Twilio: {exc}"[:300]
        attachment.save()
    if not message.has_attachments:
        message.has_attachments = True
        message.save(update_fields=["has_attachments"])
    return stored


def delete_attachments(messages) -> int:
    """Remove the stored files and rows (participant withdrawal)."""
    removed = 0
    for attachment in InboundAttachment.objects.filter(message__in=messages):
        if attachment.file_ref:
            try:
                os.remove(os.path.join(settings.PRIVATE_DATA_ROOT, attachment.file_ref))
            except OSError:
                pass
        attachment.delete()
        removed += 1
    return removed


def file_path(attachment) -> str:
    return os.path.join(settings.PRIVATE_DATA_ROOT, attachment.file_ref)


def invitation_code_owner(text: str, *, case=None, record=None):
    """(sample_case, kii_record) whose invitation code this message is, or None. A word of exactly the code's length is
    compared with that case's or record's codes; for a number on no record, with every code."""
    from apps.invitations.models import InvitationToken
    from apps.invitations.services import _verify_secret
    from apps.kii.models import KIIInvitationToken

    words = {w.upper() for w in CODE_WORD.findall(text or "")}
    if not words or len(words) > 5:
        return None
    if case is not None:
        sources = [(InvitationToken.objects.filter(sample_case=case), "main")]
    elif record is not None:
        sources = [(KIIInvitationToken.objects.filter(kii_record=record), "kii")]
    else:
        sources = [(InvitationToken.objects.all(), "main"), (KIIInvitationToken.objects.all(), "kii")]
    for tokens, which in sources:
        for owner_id, code_hash in tokens.exclude(manual_code_hash__isnull=True).values_list(
                "sample_case_id" if which == "main" else "kii_record_id", "manual_code_hash"):
            if any(_verify_secret(word, code_hash) for word in words):
                if which == "main":
                    from apps.sampling.models import SampleCase

                    return SampleCase.objects.get(pk=owner_id), None
                from apps.kii.models import KIIRecord

                return None, KIIRecord.objects.get(pk=owner_id)
    return None
