"""
Reminder queue: only ever dispatches the approved sequence, never sends
ad hoc (docs/12_CONTACT_CRM_AND_MESSAGING.md); Day 7 exhaustion moves a case
to S13 Nonresponse (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.services import issue_invitation
from apps.messaging.models import MessageLog, MessageStatus, ReminderSequenceStep
from apps.messaging.services import dispatch_due_reminders, exhaust_nonresponse_cases
from apps.sampling.models import WorkflowStatus


def _backdate_token(case, days_ago):
    token = case.invitation_tokens.order_by("-issued_at").first()
    token.issued_at = timezone.now() - timedelta(days=days_ago)
    token.save(update_fields=["issued_at"])
    return token


def test_issuing_invitation_advances_workflow_to_invitation_sent(main_case):
    from apps.sampling.services import transition_workflow_status

    transition_workflow_status(main_case, WorkflowStatus.S01_VERIFICATION_REQUIRED)
    transition_workflow_status(main_case, WorkflowStatus.S02_ORGANISATION_VERIFIED)
    transition_workflow_status(main_case, WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED)

    issue_invitation(main_case)

    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S05_INVITATION_SENT


def test_resend_does_not_regress_a_further_along_case(main_case):
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    transition_workflow_status(main_case, WorkflowStatus.S06_INVITATION_OPENED)
    transition_workflow_status(main_case, WorkflowStatus.S07_SURVEY_STARTED)

    issue_invitation(main_case, invitation_wave=2)  # a resend

    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S07_SURVEY_STARTED  # unchanged


@pytest.mark.django_db
def test_day2_reminder_dispatched_when_due_but_not_configured(main_case):
    """A respondent with a WhatsApp number on file makes the step actually
    attempt a send; with no real WhatsApp Business Platform account
    provisioned (docs/27_AGENT_EXECUTION_PLAN.md open item), it fails
    loudly into the log rather than silently pretending to send."""
    from apps.sampling.services import transition_workflow_status

    Respondent.objects.create(
        sample_case=main_case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
        whatsapp_number="+263771234567",
    )
    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=2)

    dispatched = dispatch_due_reminders()

    assert len(dispatched) == 1
    assert dispatched[0].template.name == "drp_reminder_day2"
    assert dispatched[0].status == MessageStatus.FAILED
    assert dispatched[0].triggered_by is None


def test_reminder_stays_queued_with_no_phone_on_file(main_case):
    """No Respondent/phone recorded yet -- stays QUEUED for an RA to action
    manually, rather than erroring or silently dropping."""
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=2)

    dispatched = dispatch_due_reminders()

    assert len(dispatched) == 1
    assert dispatched[0].status == MessageStatus.QUEUED


def test_reminder_never_sent_twice_for_the_same_step(main_case):
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=2)

    dispatch_due_reminders()
    second_run = dispatch_due_reminders()

    assert second_run == []
    assert MessageLog.objects.filter(sample_case=main_case).count() == 1


def test_no_reminder_before_its_day_offset(main_case):
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=1)

    assert dispatch_due_reminders() == []


def test_day7_exhaustion_moves_case_to_nonresponse(main_case):
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=8)

    exhausted = exhaust_nonresponse_cases()

    assert main_case in exhausted
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S13_NONRESPONSE


def test_exhaustion_does_not_touch_cases_within_the_sequence_window(main_case):
    from apps.sampling.services import transition_workflow_status

    for status in [
        WorkflowStatus.S01_VERIFICATION_REQUIRED,
        WorkflowStatus.S02_ORGANISATION_VERIFIED,
        WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
    ]:
        transition_workflow_status(main_case, status)
    issue_invitation(main_case)
    _backdate_token(main_case, days_ago=3)

    exhausted = exhaust_nonresponse_cases()

    assert exhausted == []
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S05_INVITATION_SENT
