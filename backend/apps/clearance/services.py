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
