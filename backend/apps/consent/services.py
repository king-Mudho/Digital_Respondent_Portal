"""
Consent capture and the gating checks other apps (kobo redirect, kii) rely
on. Explicit opt-in action required before any data is persisted beyond a
local, unsynced form state (docs/10_INVITATION_AND_CONSENT.md,
docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
"""

from django.db import transaction
from django.utils import timezone

from apps.audit.utils import log_action

from .models import ConsentDecision, ConsentRecord, ConsentType


@transaction.atomic
def record_consent(
    *,
    consent_type: str,
    decision: str,
    information_sheet_version: str,
    method: str,
    sample_case=None,
    respondent=None,
    kii_record=None,
) -> ConsentRecord:
    """Record a consent decision, for a SampleCase (respondent flow) or a
    KIIRecord (KII participants who often have no SampleCase at all -- see
    the model docstring). A later row for the same (subject, consent_type)
    supersedes the prior one -- never mutated in place, preserving the full
    audit trail."""
    if sample_case is None and kii_record is None:
        raise ValueError("One of sample_case/kii_record is required.")

    now = timezone.now()
    record = ConsentRecord.objects.create(
        sample_case=sample_case,
        respondent=respondent,
        kii_record=kii_record,
        consent_type=consent_type,
        information_sheet_version=information_sheet_version,
        decision=decision,
        method=method,
        timestamp=now,
        withdrawn_at=now if decision == ConsentDecision.WITHDRAWN else None,
    )
    log_action(
        "consent.recorded" if decision != ConsentDecision.WITHDRAWN else "consent.withdrawn",
        record,
        {
            "consent_type": consent_type,
            "decision": decision,
            "sample_id": getattr(sample_case, "sample_id", None),
            "kii_id": getattr(kii_record, "kii_id", None),
        },
    )
    return record


def latest_consent(subject, consent_type: str) -> ConsentRecord | None:
    from apps.kii.models import KIIRecord
    from apps.sampling.models import SampleCase

    filters = {"consent_type": consent_type}
    if isinstance(subject, KIIRecord):
        filters["kii_record"] = subject
    elif isinstance(subject, SampleCase):
        filters["sample_case"] = subject
    else:
        raise TypeError("subject must be a SampleCase or KIIRecord.")
    return ConsentRecord.objects.filter(**filters).order_by("-timestamp").first()


def has_given_consent(subject, consent_type: str = ConsentType.PARTICIPATION) -> bool:
    """The single check every consent-gated action (Kobo redirect, KII
    recording) must call -- never infer consent from a different
    consent_type (AGENTS.md ground rule 6). `subject` is a SampleCase or a
    KIIRecord."""
    record = latest_consent(subject, consent_type)
    return record is not None and record.decision == ConsentDecision.GIVEN
