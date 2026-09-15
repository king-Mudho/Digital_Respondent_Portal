"""
Identifier generation and Main-400/Reserve-400 integrity enforcement.

docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md is the spec. AGENTS.md ground
rule 4: every invitation-issuing code path must call is_invitable() rather
than checking SampleCase.status inline elsewhere.
"""

from django.db import models, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.audit.utils import log_action

from .models import (
    PROVINCE_CODE,
    IdentifierSequence,
    Organisation,
    ReserveStatus,
    SampleCase,
    SampleType,
    StratumDefinition,
    WorkflowStatus,
)

# Used only the first time a given province/actor_family/value_chain/
# size_class combination is seen -- an existing StratumDefinition's
# target_count is never overwritten by resolve_stratum_for_organisation().
DEFAULT_STRATUM_TARGET_COUNT = 10

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


# The verification stretch a Field Coordinator may apply to many cases at once.
BULK_TRANSITIONS = {
    WorkflowStatus.S00_SELECTED_MAIN: WorkflowStatus.S01_VERIFICATION_REQUIRED,
    WorkflowStatus.S01_VERIFICATION_REQUIRED: WorkflowStatus.S02_ORGANISATION_VERIFIED,
    WorkflowStatus.S02_ORGANISATION_VERIFIED: WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
}


@transaction.atomic
def bulk_transition_workflow_status(*, from_status: str, sample_ids=None, user=None) -> list[str]:
    """Move every MAIN case at `from_status` (or just `sample_ids` among
    them) one verification step forward, each through
    transition_workflow_status() so each case keeps its own audit trail.

    Only S00 -> S01 -> S02 -> S03. All 400 imported Main cases start at S00
    and the respondent-driven statuses (S04 onward) only begin from S03;
    one at a time that was three clicks per case, around 1,200 for the
    study. Later statuses stay per-case decisions.
    """
    to_status = BULK_TRANSITIONS.get(from_status)
    if to_status is None:
        raise InvalidWorkflowTransition(f"Bulk changes are only allowed from S00, S01 or S02, not {from_status}.")
    cases = SampleCase.objects.select_for_update().filter(sample_type=SampleType.MAIN, workflow_status=from_status)
    if sample_ids is not None:
        cases = cases.filter(sample_id__in=sample_ids)
    moved = []
    for case in cases.order_by("sample_id"):
        transition_workflow_status(case, to_status, user=user)
        moved.append(case.sample_id)
    log_action("sampling.bulk_workflow_transition", _BulkStub(f"{from_status}->{to_status}"), {
        "from": from_status, "to": to_status, "count": len(moved), "user_id": getattr(user, "id", None),
    })
    return moved


class _BulkStub:
    """The audited "object" of a bulk change: the step itself, e.g. S00->S01."""

    def __init__(self, step):
        self.pk = step


# The stretch of the workflow a respondent moves through themselves, in order.
# Every consecutive pair is a legal transition in WORKFLOW_TRANSITIONS.
RESPONDENT_PATH = [
    WorkflowStatus.S04_INVITATION_PREPARED,
    WorkflowStatus.S05_INVITATION_SENT,
    WorkflowStatus.S06_INVITATION_OPENED,
    WorkflowStatus.S07_SURVEY_STARTED,
    WorkflowStatus.S08_SURVEY_SUBMITTED,
]


def advance_case_on_respondent_event(sample_case: SampleCase, target: str) -> SampleCase:
    """Move a MAIN case forward to `target` when its respondent opens the
    link (S06), starts the questionnaire (S07) or submits it (S08).

    Until 2026-09-14 nothing did: a case reached S05 on invitation and sat
    there, so reminders kept targeting respondents who had already
    submitted, and the case page never showed progress. Steps are walked one
    legal transition at a time (a Collect submission for a case still at
    S05 passes through S06 and S07, which it genuinely did). Forward only,
    and only within the respondent path: a case not yet at S04 (verification
    steps are a researcher's call, never inferred) or already past S08 is
    left exactly as it is.
    """
    if sample_case.sample_type != SampleType.MAIN:
        return sample_case
    current = sample_case.workflow_status
    if current not in RESPONDENT_PATH or target not in RESPONDENT_PATH:
        return sample_case
    for status in RESPONDENT_PATH[RESPONDENT_PATH.index(current) + 1: RESPONDENT_PATH.index(target) + 1]:
        transition_workflow_status(sample_case, status)
    return sample_case


def advance_case_on_qa_outcome(sample_case: SampleCase, *, passed: bool) -> SampleCase:
    """S08 -> S09 when QA queries a submission; S08/S09 -> S10 when a human
    accepts it. Never moves a case backwards or out of a terminal state."""
    if sample_case.sample_type != SampleType.MAIN:
        return sample_case
    current = sample_case.workflow_status
    if passed and current in (WorkflowStatus.S08_SURVEY_SUBMITTED, WorkflowStatus.S09_QA_QUERY):
        transition_workflow_status(sample_case, WorkflowStatus.S10_QA_PASSED)
    elif not passed and current == WorkflowStatus.S08_SURVEY_SUBMITTED:
        transition_workflow_status(sample_case, WorkflowStatus.S09_QA_QUERY)
    return sample_case


@transaction.atomic
def activate_reserve(reserve_case: SampleCase, *, reason: str, activated_by, evidence_note: str = "") -> SampleCase:
    """Reserve activation always requires an authorised reason, records the
    authoriser, and writes an AuditEvent in the same transaction -- never as
    separate, potentially-skipped steps (docs/09_IDENTIFIER_AND_SAMPLING_
    CONTROL.md). No "swap" escape hatch: `reason` must be one of the five
    authorised ActivationReason values, enforced by SampleCase.clean() via
    full_clean() below.
    """
    if reserve_case.sample_type != SampleType.RESERVE:
        raise ValueError("Only a RESERVE case can be activated.")
    if reserve_case.status == ReserveStatus.ACTIVATED:
        raise ValueError("This reserve case is already activated.")

    reserve_case.status = ReserveStatus.ACTIVATED
    reserve_case.activation_reason = reason
    reserve_case.activated_by = activated_by
    reserve_case.activated_at = timezone.now()
    reserve_case.activation_evidence_note = evidence_note
    reserve_case.full_clean()
    reserve_case.save()

    log_action(
        "reserve.activated",
        reserve_case,
        {"reason": reason, "activated_by_id": getattr(activated_by, "id", None), "sample_id": reserve_case.sample_id},
    )
    return reserve_case


class InvalidMatchedCase(ValueError):
    """Raised when a Main<->Reserve pairing would break the sample design."""


@transaction.atomic
def set_matched_case(main_case: SampleCase, reserve_case, *, changed_by) -> SampleCase:
    """Pair a Main case with the Reserve case that replaces it if it drops
    out, or clear that pairing when `reserve_case` is None.

    The 400 pairs loaded by `import_quan_register` were wired directly in
    that command; this is the path for an organisation added afterwards.
    Until Sep 2026 there was no path at all short of Django admin, and
    `matched_case` was a bare FK with no validation, so the API would
    happily pair a Main case to another Main case, or hand the same
    Reserve to two different Main cases -- which silently breaks the
    reserve lock, since activating that Reserve would appear to cover
    both.

    Enforced here rather than in the serializer so every caller goes
    through the same checks and the same audit entry.
    """
    if main_case.sample_type != SampleType.MAIN:
        raise InvalidMatchedCase("Only a MAIN case can be given a matched Reserve.")

    if reserve_case is None:
        previous = main_case.matched_case
        if previous is None:
            return main_case
        main_case.matched_case = None
        main_case.save(update_fields=["matched_case"])
        log_action(
            "sample_case.match_cleared",
            main_case,
            {
                "sample_id": main_case.sample_id,
                "previous_matched_sample_id": previous.sample_id,
                "changed_by_id": getattr(changed_by, "id", None),
            },
        )
        return main_case

    if reserve_case.sample_type != SampleType.RESERVE:
        raise InvalidMatchedCase("A matched case must be a RESERVE case.")
    if reserve_case.pk == main_case.pk:
        raise InvalidMatchedCase("A case cannot be matched to itself.")
    if reserve_case.status == ReserveStatus.ACTIVATED:
        raise InvalidMatchedCase(
            "That Reserve case has already been activated and cannot be assigned as a new match."
        )

    claimed_by = (
        SampleCase.objects.filter(matched_case=reserve_case)
        .exclude(pk=main_case.pk)
        .first()
    )
    if claimed_by is not None:
        raise InvalidMatchedCase(
            f"That Reserve case is already the match for {claimed_by.sample_id}."
        )

    main_case.matched_case = reserve_case
    main_case.save(update_fields=["matched_case"])

    log_action(
        "sample_case.matched",
        main_case,
        {
            "sample_id": main_case.sample_id,
            "matched_sample_id": reserve_case.sample_id,
            # Recorded because a cross-stratum pairing weakens the
            # stratified design -- allowed (there may be no same-stratum
            # Reserve left) but never silent.
            "same_stratum": main_case.stratum_id == reserve_case.stratum_id,
            "changed_by_id": getattr(changed_by, "id", None),
        },
    )
    return main_case


def available_reserves_for(main_case: SampleCase):
    """Reserve cases that `main_case` could legitimately be paired with:
    still LOCKED, and not already claimed by another Main case. Ordered
    same-stratum first, since a replacement is meant to preserve the
    stratified design."""
    return (
        SampleCase.objects.filter(
            sample_type=SampleType.RESERVE, status=ReserveStatus.LOCKED
        )
        .filter(Q(matched_by__isnull=True) | Q(matched_by=main_case))
        .select_related("organisation", "stratum")
        .annotate(
            same_stratum=Case(
                When(stratum_id=main_case.stratum_id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("same_stratum", "sample_id")
        .distinct()
    )


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


def resolve_stratum_for_organisation(organisation: Organisation) -> StratumDefinition:
    """Get-or-create the StratumDefinition matching this organisation's own
    province/actor_family/size_class -- the approved sampling register's own
    "Stratum Allocation" sheet stratifies on exactly these three fields, not
    value_chain (2026-09-12; see StratumDefinition's docstring). A stratum is
    a derived grouping, not something an admin authors independently -- this
    lets the "register organisation + sample case" admin UI skip a separate
    stratum-picking step (and can't produce a mismatched stratum the way
    manual selection could)."""
    code = "-".join([organisation.province, organisation.actor_family, organisation.size_class])
    stratum, _ = StratumDefinition.objects.get_or_create(
        province=organisation.province,
        actor_family=organisation.actor_family,
        size_class=organisation.size_class,
        defaults={"code": code, "target_count": DEFAULT_STRATUM_TARGET_COUNT},
    )
    return stratum


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


class InvalidAssignment(Exception):
    pass


class _AssignmentRun:
    pk = "bulk_assignment"


@transaction.atomic
def bulk_assign_cases(*, to_user, from_user=None, from_unassigned=False, province=None, sample_ids=None,
                      limit=None, preview=False, user=None) -> list[str]:
    """Give Main cases to a Contact RA (or unassign them) in one audited step
    (added 2026-09-15). All 400 Main cases started on one shared account;
    reassigning them one case page at a time was 400 dropdowns.

    Filters narrow which cases move: their current owner (`from_user`, or
    `from_unassigned`), a province, explicit Sample IDs, and `limit` to move
    only the first N by Sample ID -- how a province with more cases than one
    RA can handle (Harare has 252) is split between several. `preview`
    returns the matching Sample IDs without changing anything.
    """
    if to_user is not None and (getattr(to_user.role, "name", None) != "CONTACT_RA" or not to_user.is_active):
        raise InvalidAssignment("Cases can only be assigned to an active Contact RA account.")
    if limit is not None and limit < 1:
        raise InvalidAssignment("The number of cases to move must be at least 1.")
    cases = SampleCase.objects.filter(sample_type=SampleType.MAIN)
    if from_unassigned:
        cases = cases.filter(assigned_ra__isnull=True)
    elif from_user is not None:
        cases = cases.filter(assigned_ra=from_user)
    if province:
        cases = cases.filter(organisation__province=province)
    if sample_ids is not None:
        cases = cases.filter(sample_id__in=sample_ids)
    if to_user is not None:
        cases = cases.exclude(assigned_ra=to_user)
    else:
        cases = cases.exclude(assigned_ra__isnull=True)
    ids = list(cases.order_by("sample_id").values_list("sample_id", flat=True))
    if limit is not None:
        ids = ids[:limit]
    if preview or not ids:
        return ids

    SampleCase.objects.select_for_update().filter(sample_id__in=ids).update(assigned_ra=to_user, updated_at=timezone.now())
    log_action("sampling.bulk_assignment", _AssignmentRun(), {
        "to": getattr(to_user, "username", None),
        "from": "unassigned" if from_unassigned else getattr(from_user, "username", "any"),
        "province": province or "all", "moved": len(ids), "sample_ids": ids, "user_id": getattr(user, "id", None),
    })
    return ids
