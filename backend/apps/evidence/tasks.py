"""
Generating an AI draft (apps/evidence/ai_coding.py) means an AI reading a
whole document and writing ~110 fields: minutes, not seconds. nginx closes a
browser request at 60s, so it runs here, in the Celery worker, and the review
screen polls DocumentRecord.ai_draft_status until it stops being "running".
"""

import logging

from celery import shared_task
from django.utils import timezone

from apps.audit.utils import log_action

from .ai_coding import AIDraftError, extract_document_details, generate_draft
from .models import DocumentRecord
from .services import DocumentFileError, open_source_file

logger = logging.getLogger(__name__)

RUNNING = "running"
FAILED = "failed"


def _fail(document: DocumentRecord, message: str) -> None:
    document.ai_draft_status = FAILED
    document.ai_draft_error = message
    document.ai_draft_progress = ""
    document.save(update_fields=["ai_draft_status", "ai_draft_error", "ai_draft_progress"])


def _fill_details(document, source_path, content_type, page_range, keep_title, keep_type, user_id) -> None:
    """A record made straight from a file starts with only the file name as its
    title. Read the document's front pages and fill in what it states -- title,
    author, date, type, scope, source -- so nobody retypes them. Only blank
    details are filled; a failure here never stops the draft (the person can
    edit the details on the record page)."""
    from django.utils.dateparse import parse_date

    DocumentRecord.objects.filter(pk=document.pk).update(ai_draft_progress="Step 1 of 2: reading the document's details")
    try:
        details = extract_document_details(source_path, content_type, page_range=page_range)
    except AIDraftError as exc:
        logger.warning("Could not read details for document %s: %s", document.pk, exc)
        return
    changed = []
    if details.get("title") and not keep_title:
        document.title = details["title"][:512]
        changed.append("title")
    for name in ("author_or_speaker", "geographic_scope", "value_chain", "source_url_or_reference"):
        if details.get(name) and not getattr(document, name):
            setattr(document, name, details[name][:1024 if name == "source_url_or_reference" else 255])
            changed.append(name)
    when = parse_date(details.get("publication_or_event_date", "")) if details.get("publication_or_event_date") else None
    if when and not document.publication_or_event_date:
        document.publication_or_event_date = when
        changed.append("publication_or_event_date")
    if details.get("document_type") and not keep_type:
        document.document_type = details["document_type"]
        changed.append("document_type")
    if changed:
        document.save(update_fields=[*changed])
        log_action("document.details_filled_by_ai", document, {"fields": changed, "user_id": user_id})


@shared_task
def generate_ai_draft(
    document_pk: int, user_id: int | None = None, page_range: str = "", whole_document: bool = False,
    fill_details: bool = False, keep_title: bool = False, keep_type: bool = False,
) -> None:
    from apps.accounts.models import User

    document = DocumentRecord.objects.get(pk=document_pk)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    try:
        source_path, _, source_content_type = open_source_file(document)
        if fill_details:
            _fill_details(document, source_path, source_content_type, page_range, keep_title, keep_type, user_id)
            DocumentRecord.objects.filter(pk=document_pk).update(ai_draft_progress="Step 2 of 2: drafting the coding form")
        draft = generate_draft(
            document, source_path=source_path, source_content_type=source_content_type,
            user=user, page_range=page_range, whole_document=whole_document,
            progress=lambda text: DocumentRecord.objects.filter(pk=document_pk).update(ai_draft_progress=text),
        )
    except (AIDraftError, DocumentFileError) as exc:
        _fail(document, str(exc))
        return
    except Exception:  # never leave a document stuck on "running"
        logger.exception("AI draft generation crashed for document %s", document_pk)
        _fail(document, "Something went wrong while drafting. Try again, and tell the administrator if it repeats.")
        return

    document.ai_draft = draft
    document.ai_draft_generated_at = timezone.now()
    document.ai_draft_model = draft.get("_generated_by_model", "")
    document.ai_draft_status = ""
    document.ai_draft_error = ""
    document.ai_draft_progress = ""
    document.save(update_fields=[
        "ai_draft", "ai_draft_generated_at", "ai_draft_model", "ai_draft_status", "ai_draft_error", "ai_draft_progress",
    ])
    log_action("document.ai_draft_generated", document, {
        "model": document.ai_draft_model, "user_id": user_id, "pages": page_range or "all", "parts": draft.get("_parts", 1),
    })
