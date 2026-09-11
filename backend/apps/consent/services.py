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
    sample_case,
    consent_type: str,
    decision: str,
    information_sheet_version: str,
    method: str,
    respondent=None,
) -> ConsentRecord:
    """Record a consent decision. A later row for the same
    (sample_case, consent_type) supersedes the prior one -- never mutated in
    place, preserving the full audit trail."""
    now = timezone.now()
    record = ConsentRecord.objects.create(
        sample_case=sample_case,
        respondent=respondent,
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
        {"consent_type": consent_type, "decision": decision, "sample_id": sample_case.sample_id},
    )
    return record


def latest_consent(sample_case, consent_type: str) -> ConsentRecord | None:
    return (
        ConsentRecord.objects.filter(sample_case=sample_case, consent_type=consent_type)
        .order_by("-timestamp")
        .first()
    )


def has_given_consent(sample_case, consent_type: str = ConsentType.PARTICIPATION) -> bool:
    """The single check every consent-gated action (Kobo redirect, KII
    recording) must call -- never infer consent from a different
    consent_type (AGENTS.md ground rule 6)."""
    record = latest_consent(sample_case, consent_type)
    return record is not None and record.decision == ConsentDecision.GIVEN
