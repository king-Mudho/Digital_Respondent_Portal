from django.utils import timezone

from apps.audit.utils import log_action
from apps.sampling.services import next_sequence

from .models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord


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
