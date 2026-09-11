"""
Identifier generation and Main-400/Reserve-400 integrity enforcement.

docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md is the spec. AGENTS.md ground
rule 4: every invitation-issuing code path must call is_invitable() rather
than checking SampleCase.status inline elsewhere.
"""

from django.db import models, transaction

from apps.audit.utils import log_action

from django.utils import timezone

from .models import (
    PROVINCE_CODE,
    IdentifierSequence,
    Organisation,
    ReserveStatus,
    SampleCase,
    SampleType,
    WorkflowStatus,
)

# S00-S16 state-transition table (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).
# S12-S15 -> S16 represents "approved follow-up sequence exhausted"; the
# messaging app's reminder-sequence exhaustion check (Phase 7,
# docs/12_CONTACT_CRM_AND_MESSAGING.md) gates *when* that transition is
# offered in the UI/service layer, not whether it is structurally valid --
# this table only encodes structural validity.
WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    WorkflowStatus.S00_SELECTED_MAIN: {WorkflowStatus.S01_VERIFICATION_REQUIRED},
    WorkflowStatus.S01_VERIFICATION_REQUIRED: {
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S15_DUPLICATE_INACTIVE,
    },
    WorkflowStatus.S02_ORGANISATION_VERIFIED: {
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
        WorkflowStatus.S14_INELIGIBLE,
        WorkflowStatus.S15_DUPLICATE_INACTIVE,
    },
    WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED: {
        WorkflowStatus.S04_INVITATION_PREPARED,
        WorkflowStatus.S14_INELIGIBLE,
    },
    WorkflowStatus.S04_INVITATION_PREPARED: {WorkflowStatus.S05_INVITATION_SENT},
    WorkflowStatus.S05_INVITATION_SENT: {
        WorkflowStatus.S06_INVITATION_OPENED,
        WorkflowStatus.S12_REFUSED,
        WorkflowStatus.S13_NONRESPONSE,
    },
    WorkflowStatus.S06_INVITATION_OPENED: {
        WorkflowStatus.S07_SURVEY_STARTED,
        WorkflowStatus.S12_REFUSED,
        WorkflowStatus.S13_NONRESPONSE,
    },
    WorkflowStatus.S07_SURVEY_STARTED: {
        WorkflowStatus.S08_SURVEY_SUBMITTED,
        WorkflowStatus.S12_REFUSED,
        WorkflowStatus.S13_NONRESPONSE,
    },
    WorkflowStatus.S08_SURVEY_SUBMITTED: {
        WorkflowStatus.S09_QA_QUERY,
        WorkflowStatus.S10_QA_PASSED,
    },
    WorkflowStatus.S09_QA_QUERY: {WorkflowStatus.S10_QA_PASSED},
    WorkflowStatus.S10_QA_PASSED: {WorkflowStatus.S11_COMPLETED},
    WorkflowStatus.S11_COMPLETED: set(),
    WorkflowStatus.S12_REFUSED: {WorkflowStatus.S16_RESERVE_ELIGIBLE},
    WorkflowStatus.S13_NONRESPONSE: {WorkflowStatus.S16_RESERVE_ELIGIBLE},
    WorkflowStatus.S14_INELIGIBLE: {WorkflowStatus.S16_RESERVE_ELIGIBLE},
    WorkflowStatus.S15_DUPLICATE_INACTIVE: {WorkflowStatus.S16_RESERVE_ELIGIBLE},
    WorkflowStatus.S16_RESERVE_ELIGIBLE: set(),
}


class InvalidWorkflowTransition(Exception):
    pass


def transition_workflow_status(sample_case: SampleCase, new_status: str, *, user=None) -> SampleCase:
    """Apply a validated S00-S16 transition; reject and audit-log an invalid
    one rather than silently applying it (docs/09_IDENTIFIER_AND_SAMPLING_
    CONTROL.md)."""
    if sample_case.sample_type != SampleType.MAIN:
        raise InvalidWorkflowTransition("Only MAIN cases have a workflow_status.")

    current = sample_case.workflow_status
    allowed = WORKFLOW_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        log_action(
            "sampling.invalid_workflow_transition",
            sample_case,
            {"from": current, "attempted": new_status, "user_id": getattr(user, "id", None)},
        )
        raise InvalidWorkflowTransition(f"Cannot transition {current} -> {new_status}.")

    sample_case.workflow_status = new_status
    sample_case.status = new_status
    sample_case.full_clean()
    sample_case.save(update_fields=["workflow_status", "status", "updated_at"])
    return sample_case


def is_invitable(sample_case: SampleCase) -> bool:
    """The single enforcement point for the Main-400/Reserve-400 integrity
    rule (AGENTS.md ground rule 4). Every invitation-issuing code path must
    call this -- never check SampleCase.status inline elsewhere.
    """
    if sample_case.sample_type == SampleType.RESERVE:
        return sample_case.status == ReserveStatus.ACTIVATED
    return True


@transaction.atomic
def next_sequence(key: str) -> int:
    seq, _ = IdentifierSequence.objects.select_for_update().get_or_create(key=key)
    seq.last_value = models.F("last_value") + 1
    seq.save(update_fields=["last_value"])
    seq.refresh_from_db(fields=["last_value"])
    return seq.last_value


def generate_master_id(province: str) -> str:
    """MID-<province-code(2)>-<sequence(6)>, e.g. MID-HA-000418. DB-generated,
    unique within the province code -- collision structurally impossible."""
    code = PROVINCE_CODE[province]
    seq = next_sequence(f"MASTER_ID:{code}")
    return f"MID-{code}-{seq:06d}"


def generate_sample_id(year: int) -> str:
    """SID-<year(4)>-<sequence(6)>, e.g. SID-2026-000418."""
    seq = next_sequence(f"SAMPLE_ID:{year}")
    return f"SID-{year}-{seq:06d}"


def create_organisation(*, province: str, **fields) -> Organisation:
    """The only sanctioned way to create an Organisation -- generates and
    assigns master_id, which is never user-entered
    (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md)."""
    org = Organisation(master_id=generate_master_id(province), province=province, **fields)
    org.full_clean()
    org.save()
    return org


def create_sample_case(
    *, organisation: Organisation, stratum, sample_type: str, year: int | None = None, **fields
) -> SampleCase:
    """The only sanctioned way to create a SampleCase -- generates and
    assigns sample_id and seeds the correct initial status for MAIN
    (S00_SELECTED_MAIN) or RESERVE (LOCKED)."""
    year = year or timezone.now().year
    if sample_type == SampleType.MAIN:
        fields.setdefault("workflow_status", WorkflowStatus.S00_SELECTED_MAIN)
        fields.setdefault("status", WorkflowStatus.S00_SELECTED_MAIN)
    else:
        fields.setdefault("status", ReserveStatus.LOCKED)

    case = SampleCase(
        sample_id=generate_sample_id(year),
        organisation=organisation,
        stratum=stratum,
        sample_type=sample_type,
        **fields,
    )
    case.full_clean()
    case.save()
    return case
