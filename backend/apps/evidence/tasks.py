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

from .ai_coding import AIDraftError, generate_draft
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


@shared_task
def generate_ai_draft(
    document_pk: int, user_id: int | None = None, page_range: str = "", whole_document: bool = False,
) -> None:
    from apps.accounts.models import User

    document = DocumentRecord.objects.get(pk=document_pk)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    try:
        source_path, _, source_content_type = open_source_file(document)
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
