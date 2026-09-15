"""
Recording a participant's withdrawal (docs/10_INVITATION_AND_CONSENT.md
"Withdrawal is a first-class action"; docs/18 retention and withdrawal).

Until 2026-09-14 the data model allowed a WITHDRAWN consent row but nothing
could create one for a case: no staff screen, no staff endpoint. A
respondent who phoned to withdraw could not be recorded as withdrawn, their
invitation stayed live and the reminder sequence would have kept messaging
them.
"""

from django.db import transaction

from apps.audit.utils import log_action
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import revoke_token
from apps.sampling.models import SampleCase, SampleType, WorkflowStatus
from apps.sampling.services import WORKFLOW_TRANSITIONS, transition_workflow_status

from .models import ConsentDecision, ConsentMethod, ConsentType
from .services import latest_consent, record_consent

CONTACT_FIELDS = ("phone", "whatsapp_number", "email", "gatekeeper_contact")


class AlreadyWithdrawn(ValueError):
    pass


@transaction.atomic
def record_withdrawal(sample_case: SampleCase, *, reason: str, method: str = ConsentMethod.VERBAL_RA_RECORDED,
                      recorded_by=None) -> dict:
    """Withdraw a case's participant and apply the data-handling steps the
    portal can apply on its own:

    1. a WITHDRAWN participation consent row, superseding the GIVEN one;
    2. every open invitation revoked, so the link stops working and no
       reminder is offered;
    3. the case moved to S12 Refused where the workflow allows it (a case
       already submitted keeps its status);
    4. respondent contact details (phone, WhatsApp, email, gatekeeper
       contact) erased, per docs/18.

    Submitted questionnaire data in KoboToolbox and the portal is kept
    (archived, audit trail) but left out of analysis -- PI decision, 15 Sep
    2026: omitted from the analysis export, flagged in the operational export
    and in the PI's KoboToolbox workbook and PDF ZIP.
    """
    if not reason.strip():
        raise ValueError("A reason is required to record a withdrawal.")
    current = latest_consent(sample_case, ConsentType.PARTICIPATION)
    if current is not None and current.decision == ConsentDecision.WITHDRAWN:
        raise AlreadyWithdrawn("This participant has already withdrawn.")

    record_consent(
        sample_case=sample_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.WITHDRAWN,
        information_sheet_version=current.information_sheet_version if current else "",
        method=method,
    )

    open_tokens = InvitationToken.objects.filter(sample_case=sample_case).exclude(
        status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED]
    )
    revoked = 0
    for token in open_tokens:
        revoke_token(token, "Participant withdrew", revoked_by=recorded_by)
        revoked += 1

    moved_to = None
    if (
        sample_case.sample_type == SampleType.MAIN
        and WorkflowStatus.S12_REFUSED in WORKFLOW_TRANSITIONS.get(sample_case.workflow_status, set())
    ):
        transition_workflow_status(sample_case, WorkflowStatus.S12_REFUSED, user=recorded_by)
        moved_to = WorkflowStatus.S12_REFUSED

    erased = 0
    for respondent in sample_case.respondents.all():
        changed = [field for field in CONTACT_FIELDS if getattr(respondent, field)]
        for field in changed:
            setattr(respondent, field, "")
        if changed:
            respondent.save(update_fields=[*changed, "updated_at"])
            erased += 1

    summary = {
        "sample_id": sample_case.sample_id,
        "reason": reason,
        "method": method,
        "invitations_revoked": revoked,
        "workflow_status": sample_case.workflow_status,
        "moved_to_refused": moved_to is not None,
        "respondents_contact_erased": erased,
        "recorded_by_id": getattr(recorded_by, "id", None),
    }
    log_action("consent.withdrawal_processed", sample_case, summary)
    return summary
