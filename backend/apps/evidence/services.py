import os
import uuid
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action
from apps.sampling.services import next_sequence

from .models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord

# Types a Documentary RA plausibly needs to attach: scanned/photographed
# documents, platform screenshots, office files, and KII-style recordings
# for media sources. Anything else is refused rather than silently accepted
# -- this is a research evidence store, not a general file dump.
ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".m4a", ".wav", ".mp4", ".txt", ".csv",
}


class DocumentFileError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def generate_document_id() -> str:
    """DOC-<sequence(4)>, e.g. DOC-0042. System-generated, never user-entered,
    same DB-sequence approach as Master_ID/Sample_ID/KII_ID."""
    seq = next_sequence("DOCUMENT_ID")
    return f"DOC-{seq:04d}"


class DocumentWorkflowError(Exception):
    pass


def record_authenticity_assessment(document: DocumentRecord, assessment: str, *, reviewer) -> DocumentRecord:
    """Every document goes through authenticity_assessment
    (UNVERIFIED -> VERIFIED or DISPUTED) before it can move to
    qa_status=INCLUDED. A reviewer is always recorded. A DISPUTED document
    is retained, never silently deleted -- the dispute reason belongs in
    interpretive_memo, for the PI to adjudicate
    (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md)."""
    document.authenticity_assessment = assessment
    document.reviewer = reviewer
    if assessment in (AuthenticityAssessment.VERIFIED, AuthenticityAssessment.DISPUTED):
        document.verified_at = timezone.now()
    document.save(update_fields=["authenticity_assessment", "reviewer", "verified_at"])
    log_action(
        "document.authenticity_assessed",
        document,
        {"assessment": assessment, "reviewer_id": getattr(reviewer, "id", None)},
    )
    return document


def set_qa_status(document: DocumentRecord, qa_status: str, *, reviewer) -> DocumentRecord:
    """A document can only move to INCLUDED once authenticity has been
    assessed (not left UNVERIFIED) -- a DISPUTED document may still be
    reviewed and excluded, but never silently included."""
    if qa_status == DocumentQAStatus.INCLUDED and document.authenticity_assessment == AuthenticityAssessment.UNVERIFIED:
        raise DocumentWorkflowError("Cannot include a document before its authenticity has been assessed.")

    document.qa_status = qa_status
    document.reviewer = reviewer
    document.save(update_fields=["qa_status", "reviewer"])
    log_action(
        "document.qa_status_set",
        document,
        {"qa_status": qa_status, "reviewer_id": getattr(reviewer, "id", None)},
    )
    return document


# --- KoboToolbox Document Analysis Tool: prefilled coding link --------------

def documents_form_is_configured() -> bool:
    return bool((settings.KOBO_DOCUMENTS_FORM_URL or "").strip())


def build_document_coding_url(document: DocumentRecord) -> str | None:
    """Prefills the KoboToolbox Document, Digital Platform & Media Analysis
    Tool with this record's DOC-ID and known fields, so coding never starts
    from a blank Section A: a Documentary RA doesn't retype the DOC-ID by
    hand, and a typo can no longer make the completed form fail to match
    back up with this record on the document's page
    (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md).

    Same ?d[<data column>]=value prefill mechanism as the main questionnaire
    (apps/kobo/services.py build_redirect_url) -- but here the fields sit
    inside the tool's `section_a` group, so the data-column names need that
    group path (support.kobotoolbox.org/data_through_webforms.html).
    Returns None when KOBO_DOCUMENTS_FORM_URL hasn't been set yet.
    """
    if not documents_form_is_configured():
        return None
    form_url = settings.KOBO_DOCUMENTS_FORM_URL.strip().rstrip("/")
    fields = {
        "section_a/DOC_ID": document.document_id,
        "section_a/org_author": document.author_or_speaker,
        "section_a/title_evidence_unit": document.title,
        "section_a/url_file_platform": document.source_url_or_reference,
    }
    if document.publication_or_event_date:
        fields["section_a/pub_event_date"] = document.publication_or_event_date.isoformat()
    # DOC_ID is server-generated and always present; the others are
    # optional record fields, left for the RA to fill in Kobo when blank.
    query = "&".join(f"d[{key}]={quote(str(value), safe='')}" for key, value in fields.items() if value)
    separator = "&" if "?" in form_url else "?"
    return f"{form_url}{separator}{query}"


# --- Source file upload/download --------------------------------------------

def save_source_file(document: DocumentRecord, uploaded_file, *, user) -> DocumentRecord:
    """Stores the source file (a scan, a platform screenshot, a recording)
    privately under PRIVATE_DATA_ROOT/documents/ -- outside any web-served
    directory, downloadable only through the permission-checked, audited
    DocumentFileView, exactly the pattern already used for raw Kobo payloads
    (apps/qa/services.py). Replaces any previous file for this document: the
    register keeps one current source per record, not a version history.
    """
    original_name = uploaded_file.name or "upload"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise DocumentFileError(
            "unsupported_file_type",
            f"'{ext or 'that type'}' files aren't accepted. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}.",
        )
    max_bytes = settings.DOCUMENT_MAX_UPLOAD_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise DocumentFileError(
            "file_too_large",
            f"That file is larger than the {settings.DOCUMENT_MAX_UPLOAD_MB} MB limit.",
        )

    if document.source_file_ref:
        old_path = os.path.join(settings.PRIVATE_DATA_ROOT, document.source_file_ref)
        if os.path.exists(old_path):
            os.remove(old_path)

    # document_id (DOC-\d{4}) is always server-generated, never user text,
    # so it's safe to use directly in the path -- and the stored filename is
    # a fresh UUID, never the original name, so nothing user-supplied ever
    # reaches the filesystem path.
    stored_name = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join("documents", document.document_id, stored_name)
    abs_path = os.path.join(settings.PRIVATE_DATA_ROOT, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)

    had_file = bool(document.source_file_ref)
    document.source_file_ref = rel_path
    document.source_file_name = original_name
    document.source_file_content_type = uploaded_file.content_type or "application/octet-stream"
    document.source_file_size = uploaded_file.size
    document.source_file_uploaded_at = timezone.now()
    # A draft written from the file being replaced describes the wrong
    # document now -- leaving it would let it be reviewed and submitted as
    # if it matched the new file.
    draft_discarded = had_file and _discard_unsubmitted_draft(document)
    _clear_draft_job_state(document)
    document.save(update_fields=[
        "source_file_ref", "source_file_name", "source_file_content_type",
        "source_file_size", "source_file_uploaded_at",
        "ai_draft", "ai_draft_generated_at", "ai_draft_model", "ai_draft_status", "ai_draft_error", "ai_draft_progress",
    ])
    log_action("document.file_uploaded", document, {
        "filename": original_name, "size": uploaded_file.size, "user_id": getattr(user, "id", None),
        "ai_draft_discarded": draft_discarded,
    })
    return document


def _discard_unsubmitted_draft(document: DocumentRecord) -> bool:
    """Clears the AI draft unless it has already been submitted to
    KoboToolbox -- a submitted draft is kept as the record of exactly what
    was filed. Returns whether a draft was discarded. Caller saves."""
    if document.kobo_submitted_at or not document.ai_draft:
        return False
    document.ai_draft = {}
    document.ai_draft_generated_at = None
    document.ai_draft_model = ""
    return True


def _clear_draft_job_state(document: DocumentRecord) -> None:
    """A failed/running note about the old file means nothing for the new one."""
    document.ai_draft_status = ""
    document.ai_draft_error = ""
    document.ai_draft_progress = ""


def remove_source_file(document: DocumentRecord, *, user) -> DocumentRecord:
    """Deletes the stored source file (e.g. the wrong document was
    uploaded) and clears its metadata. The register then shows 'No file
    uploaded yet' again. An unsubmitted AI draft made from that file is
    discarded with it; the removal is audited with the file name."""
    if not document.source_file_ref:
        raise DocumentFileError("not_found", "No file has been uploaded for this document.", 404)
    path = os.path.join(settings.PRIVATE_DATA_ROOT, document.source_file_ref)
    if os.path.exists(path):
        os.remove(path)
    removed_name = document.source_file_name
    document.source_file_ref = ""
    document.source_file_name = ""
    document.source_file_content_type = ""
    document.source_file_size = None
    document.source_file_uploaded_at = None
    draft_discarded = _discard_unsubmitted_draft(document)
    _clear_draft_job_state(document)
    document.save(update_fields=[
        "source_file_ref", "source_file_name", "source_file_content_type",
        "source_file_size", "source_file_uploaded_at",
        "ai_draft", "ai_draft_generated_at", "ai_draft_model", "ai_draft_status", "ai_draft_error", "ai_draft_progress",
    ])
    log_action("document.file_removed", document, {
        "filename": removed_name, "user_id": getattr(user, "id", None), "ai_draft_discarded": draft_discarded,
    })
    return document


def open_source_file(document: DocumentRecord) -> tuple[str, str, str]:
    """Returns (absolute_path, download_filename, content_type) for the
    stored source file, or raises DocumentFileError if there isn't one."""
    if not document.source_file_ref:
        raise DocumentFileError("not_found", "No file has been uploaded for this document.", 404)
    abs_path = os.path.join(settings.PRIVATE_DATA_ROOT, document.source_file_ref)
    if not os.path.exists(abs_path):
        raise DocumentFileError("not_found", "The stored file is missing on the server.", 404)
    return abs_path, document.source_file_name, document.source_file_content_type
