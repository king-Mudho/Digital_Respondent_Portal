"""File upload/download for ClearanceDocument -- the same private-storage pattern as
apps.evidence.services.save_source_file/open_source_file, kept as its own copy rather than a shared helper
because the two registers must never be coupled (see the module docstring in models.py)."""

import os
import uuid

from django.conf import settings

from .models import ClearanceDocument

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_UPLOAD_MB = 20


class ClearanceFileError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def save_file(document: ClearanceDocument, uploaded_file, *, user) -> ClearanceDocument:
    original_name = uploaded_file.name or "upload"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ClearanceFileError(
            "unsupported_file_type",
            f"'{ext or 'that type'}' files aren't accepted. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}.",
        )
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ClearanceFileError("file_too_large", f"That file is larger than the {MAX_UPLOAD_MB} MB limit.")

    if document.file_ref:
        old_path = os.path.join(settings.PRIVATE_DATA_ROOT, document.file_ref)
        if os.path.exists(old_path):
            os.remove(old_path)

    folder = os.path.join(settings.PRIVATE_DATA_ROOT, "clearance")
    os.makedirs(folder, exist_ok=True)
    rel_path = os.path.join("clearance", f"{uuid.uuid4().hex}{ext}")
    abs_path = os.path.join(settings.PRIVATE_DATA_ROOT, rel_path)
    with open(abs_path, "wb") as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    document.file_ref = rel_path
    document.file_name = original_name
    document.file_content_type = uploaded_file.content_type or "application/octet-stream"
    document.file_size = uploaded_file.size
    from django.utils import timezone

    document.file_uploaded_at = timezone.now()
    document.save(update_fields=["file_ref", "file_name", "file_content_type", "file_size", "file_uploaded_at", "updated_at"])
    return document


def open_file(document: ClearanceDocument) -> tuple[str, str, str]:
    if not document.file_ref:
        raise ClearanceFileError("not_found", "No file has been uploaded for this document.", 404)
    abs_path = os.path.join(settings.PRIVATE_DATA_ROOT, document.file_ref)
    if not os.path.exists(abs_path):
        raise ClearanceFileError("not_found", "The stored file is missing on the server.", 404)
    return abs_path, document.file_name, document.file_content_type


def remove_file(document: ClearanceDocument) -> ClearanceDocument:
    if not document.file_ref:
        raise ClearanceFileError("not_found", "No file has been uploaded for this document.", 404)
    abs_path = os.path.join(settings.PRIVATE_DATA_ROOT, document.file_ref)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    document.file_ref = document.file_name = document.file_content_type = ""
    document.file_size = document.file_uploaded_at = None
    document.save(update_fields=["file_ref", "file_name", "file_content_type", "file_size", "file_uploaded_at", "updated_at"])
    return document


# --- The letters every participant may see, sent with the invitation itself (PI, 19 Oct 2026) -------------------------
#
# A key informant who had left an invitation unanswered agreed to meet once he was sent the study's letters: people
# trust an approach that shows its authorisation up front. So the letters a participant can open on their link's
# information page (public, active, with a file) also go with the invitation: attached to the email, and as one
# combined PDF above the WhatsApp introduction (a template with a document, which WhatsApp fetches from a URL).

PACK_NAME = "ABF-FST-Study-Letters.pdf"
_pack_cache: dict = {}


def respondent_letters() -> list[ClearanceDocument]:
    """The letters a participant may see: public, active, with a file on disk -- oldest first."""
    letters = []
    for doc in ClearanceDocument.objects.filter(is_public=True, active=True).order_by("issue_date", "pk"):
        if doc.file_ref and os.path.exists(os.path.join(settings.PRIVATE_DATA_ROOT, doc.file_ref)):
            letters.append(doc)
    return letters


def letter_attachments() -> list[tuple[str, bytes, str]]:
    """(file name, content, type) of each letter, to attach to an email."""
    out = []
    for doc in respondent_letters():
        path, filename, content_type = open_file(doc)
        with open(path, "rb") as fh:
            out.append((filename, fh.read(), content_type or "application/pdf"))
    return out


def letters_pack() -> bytes | None:
    """The PDF letters combined into one PDF, in order; None when there are none. Rebuilt when a letter changes."""
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    docs = [d for d in respondent_letters() if (d.file_content_type or "").endswith("pdf") or d.file_name.lower().endswith(".pdf")]
    if not docs:
        return None
    key = tuple((d.pk, d.file_ref) for d in docs)
    if key not in _pack_cache:
        writer = PdfWriter()
        for doc in docs:
            path, _, _ = open_file(doc)
            for page in PdfReader(path).pages:
                writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        _pack_cache.clear()
        _pack_cache[key] = out.getvalue()
    return _pack_cache[key]


def letters_pack_url() -> str:
    """Where WhatsApp fetches the combined letters, or "" until STUDY_LETTERS_KEY is set."""
    key = (getattr(settings, "STUDY_LETTERS_KEY", "") or "").strip()
    if not key:
        return ""
    return f"https://{settings.APP_DOMAIN}/api/v1/study-letters/{key}/{PACK_NAME}"
