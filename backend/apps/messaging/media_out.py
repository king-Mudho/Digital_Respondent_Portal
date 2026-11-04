"""Documents, pictures, videos and voice notes sent on WhatsApp from Communications (2026-11-04).

WhatsApp takes a file only inside the same 24 hours as a written reply (communications.send_media checks that, and
everything else a written message must pass, before this module is reached). Each file is checked against what
WhatsApp accepts -- by its first bytes, not only its name -- kept in PRIVATE_DATA_ROOT (never a web-served directory),
and handed to Twilio as a signed link that works for WHATSAPP_MEDIA_LINK_MINUTES. The link is the only credential, so
it names one file and cannot be altered or reused after it expires. A voice note recorded in Chrome is turned from
WebM into Ogg first (apps/messaging/voice.py).
"""

import os
import re
import uuid

from django.conf import settings
from django.core import signing
from django.utils import timezone

from . import twilio_client as tw
from .models import AttachmentKind, OutboundAttachment

FOLDER = "whatsapp_outbound"
SALT = "drp.whatsapp-outbound-media"
CAPTION_MAX = 1024  # WhatsApp's own limit on a caption

# extension: (content type, kind, how to recognise the file's first bytes)
ACCEPTED = {
    ".jpg": ("image/jpeg", AttachmentKind.IMAGE, "jpeg"), ".jpeg": ("image/jpeg", AttachmentKind.IMAGE, "jpeg"),
    ".png": ("image/png", AttachmentKind.IMAGE, "png"),
    ".mp4": ("video/mp4", AttachmentKind.VIDEO, "mp4"), ".3gp": ("video/3gpp", AttachmentKind.VIDEO, "mp4"),
    ".ogg": ("audio/ogg", AttachmentKind.VOICE, "ogg"), ".opus": ("audio/ogg", AttachmentKind.VOICE, "ogg"),
    ".mp3": ("audio/mpeg", AttachmentKind.VOICE, "mp3"), ".m4a": ("audio/mp4", AttachmentKind.VOICE, "mp4"),
    ".aac": ("audio/aac", AttachmentKind.VOICE, "mp3"), ".amr": ("audio/amr", AttachmentKind.VOICE, "amr"),
    ".pdf": ("application/pdf", AttachmentKind.DOCUMENT, "pdf"),
    ".doc": ("application/msword", AttachmentKind.DOCUMENT, "ole"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", AttachmentKind.DOCUMENT, "zip"),
    ".xls": ("application/vnd.ms-excel", AttachmentKind.DOCUMENT, "ole"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", AttachmentKind.DOCUMENT, "zip"),
    ".ppt": ("application/vnd.ms-powerpoint", AttachmentKind.DOCUMENT, "ole"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", AttachmentKind.DOCUMENT, "zip"),
    ".txt": ("text/plain", AttachmentKind.DOCUMENT, "text"),
}
# What people commonly try that WhatsApp refuses, with what to do instead.
REFUSED = {
    ".heic": "iPhone HEIC photos can't be sent on WhatsApp from here. Save it as JPG (or take a screenshot) and try again.",
    ".heif": "iPhone HEIF photos can't be sent on WhatsApp from here. Save it as JPG and try again.",
    ".mov": "MOV videos can't be sent on WhatsApp. Save it as MP4 and try again.",
    ".webp": "WEBP pictures can't be sent on WhatsApp from here. Save it as JPG or PNG.",
    ".gif": "GIF pictures can't be sent on WhatsApp from here. Save it as JPG or PNG, or as an MP4 video.",
    ".wav": "WAV sound files can't be sent on WhatsApp. Save it as MP3 or record a voice note here instead.",
    ".zip": "ZIP files can't be sent on WhatsApp. Send the documents inside it one by one.",
}
EXTENSIONS = sorted(ACCEPTED)
# A browser's own recording: Chrome/Edge (WebM, converted), Firefox (Ogg), Safari (MP4/AAC).
RECORDING_TYPES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/mpeg": ".mp3"}


class MediaError(ValueError):
    pass


def _looks_like(sniff: str, data: bytes) -> bool:
    if sniff == "jpeg":
        return data[:3] == b"\xff\xd8\xff"
    if sniff == "png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if sniff == "pdf":
        return data[:5] == b"%PDF-"
    if sniff == "zip":
        return data[:4] == b"PK\x03\x04"
    if sniff == "ole":
        return data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if sniff == "mp4":
        return data[4:8] == b"ftyp"
    if sniff == "ogg":
        return data[:4] == b"OggS"
    if sniff == "amr":
        return data[:5] == b"#!AMR"
    if sniff == "mp3":  # ID3 tag, or an MPEG / ADTS frame sync
        return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    if sniff == "text":
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in data[:4096]
    return False


def safe_filename(name: str, ext: str) -> str:
    """What the person sees as the file's name: letters, digits, spaces, dots, dashes; never a path."""
    stem = os.path.splitext(os.path.basename((name or "").replace("\\", "/")))[0]
    stem = re.sub(r"[^A-Za-z0-9 ._()-]+", "", stem).strip(" .")[:80] or "file"
    return f"{stem}{ext}"


def _mb(value: float) -> int:
    return int(value * 1024 * 1024)


def prepare(name: str, data: bytes, *, recording_type: str = "") -> dict:
    """{content_type, kind, filename, data} for one file, or MediaError saying what to do instead. A recording made in
    the browser is named by its content type (recording_type); anything else by its extension."""
    if not data:
        raise MediaError(f"\"{name or 'The file'}\" is empty.")
    if recording_type:
        ext = RECORDING_TYPES.get(recording_type.split(";")[0].strip().lower())
        if ext is None:
            raise MediaError("This browser records sound in a format WhatsApp can't take. Try Chrome, Edge or Firefox.")
        if ext == ".webm":
            from .voice import VoiceError, webm_to_ogg

            try:
                data = webm_to_ogg(data)
            except VoiceError as exc:
                raise MediaError(f"The voice note could not be prepared: {exc}") from exc
            ext = ".ogg"
        stamp = timezone.localtime().strftime("%Y-%m-%d %H%M")
        name = f"Voice note {stamp}{ext}"
    ext = os.path.splitext(name or "")[1].lower()
    if ext in REFUSED:
        raise MediaError(REFUSED[ext])
    if ext not in ACCEPTED:
        raise MediaError(f"\"{name}\" can't be sent on WhatsApp. It takes pictures (JPG, PNG), videos (MP4), sound "
                         "(MP3, OGG, M4A, AAC, AMR) and documents (PDF, Word, Excel, PowerPoint, TXT).")
    content_type, kind, sniff = ACCEPTED[ext]
    if not _looks_like(sniff, data):
        raise MediaError(f"\"{name}\" is not really a {ext[1:].upper()} file, so WhatsApp would refuse it.")
    limit = settings.WHATSAPP_IMAGE_MAX_MB if kind == AttachmentKind.IMAGE else settings.WHATSAPP_MEDIA_MAX_MB
    if len(data) > _mb(limit):
        raise MediaError(f"\"{name}\" is {len(data) / 1048576:.1f} MB; WhatsApp takes "
                         f"{'pictures' if kind == AttachmentKind.IMAGE else 'files'} up to {limit:g} MB.")
    return {"content_type": content_type, "kind": kind, "filename": safe_filename(name, ext), "data": data}


def store(prepared: dict) -> str:
    """Keeps the file privately; returns its path relative to PRIVATE_DATA_ROOT."""
    ext = os.path.splitext(prepared["filename"])[1]
    rel = os.path.join(FOLDER, timezone.now().strftime("%Y%m"), f"{uuid.uuid4().hex}{ext}")
    path = os.path.join(settings.PRIVATE_DATA_ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(prepared["data"])
    return rel


def discard(rel: str) -> None:
    try:
        os.remove(os.path.join(settings.PRIVATE_DATA_ROOT, rel))
    except OSError:
        pass


def signed_url(rel: str, content_type: str, filename: str) -> str:
    """The link Twilio fetches the file from. The file's name goes last, so WhatsApp shows it on a document."""
    token = signing.dumps({"f": rel, "t": content_type}, salt=SALT, compress=False)
    return f"{tw.media_base_url()}{token}/{filename}"


def resolve(token: str) -> tuple[str, str] | None:
    """(absolute path, content type) for a valid, unexpired link, or None."""
    try:
        payload = signing.loads(token, salt=SALT, max_age=settings.WHATSAPP_MEDIA_LINK_MINUTES * 60)
    except signing.BadSignature:  # also SignatureExpired
        return None
    rel = str(payload.get("f", ""))
    root = os.path.realpath(os.path.join(settings.PRIVATE_DATA_ROOT, FOLDER))
    path = os.path.realpath(os.path.join(settings.PRIVATE_DATA_ROOT, rel))
    if not path.startswith(root + os.sep) or not os.path.exists(path):
        return None
    return path, str(payload.get("t") or "application/octet-stream")


def label(kind: str, filename: str) -> str:
    return "[Voice note]" if kind == AttachmentKind.VOICE and filename.startswith("Voice note") else \
        f"[{AttachmentKind(kind).label}: {filename}]"


def delete_for(messages) -> int:
    """Remove the stored files and rows of these sent messages (participant withdrawal)."""
    removed = 0
    for attachment in OutboundAttachment.objects.filter(message__in=messages):
        discard(attachment.file_ref)
        attachment.delete()
        removed += 1
    return removed
