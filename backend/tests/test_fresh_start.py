"""manage.py fresh_start_outreach (PI decision, 2026-10-14): Main cases contacted but never completed go back to S03 so
they can be asked afresh on the new WhatsApp line. Under test: exactly the right cases move (never one with a
submission, a refusal, an unverified case or a Reserve), every link they hold is revoked so no old reminder goes out,
consent records and respondents are kept, each case is audited, a dry run changes nothing, a second run does nothing,
and a reset case can then be introduced.
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.consent.models import ConsentRecord
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation
from apps.kobo.models import QUANSubmission
from apps.messaging.services import dispatch_due_reminders
from apps.sampling.models import SampleCase, SampleType
from apps.sampling.services import create_sample_case

pytestmark = pytest.mark.django_db
REASON = "New study WhatsApp line: ask everyone afresh"


def _case(organisation, stratum, status, *, phone="0771234567", sample_type=SampleType.MAIN):
    case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=sample_type, year=2026)
    Respondent.objects.create(sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD, is_eligible=True, phone=phone)
    SampleCase.objects.filter(pk=case.pk).update(workflow_status="S03")
    case.refresh_from_db()
    if status not in ("S00", "S03"):
        issue_invitation(case)  # S03 -> S05 through the real path
    SampleCase.objects.filter(pk=case.pk).update(workflow_status=status)
    case.refresh_from_db()
    return case


def _run(*args):
    out = StringIO()
    call_command("fresh_start_outreach", "--reason", REASON, *args, stdout=out)
    return out.getvalue()


def test_contacted_cases_return_to_s03_and_completed_refused_unverified_and_reserves_never_move(organisation, stratum, activated_reserve_case):
    moving = {s: _case(organisation, stratum, s) for s in ("S05", "S06", "S07", "S13")}
    completed = _case(organisation, stratum, "S10")
    QUANSubmission.objects.create(sample_case=completed, kobo_submission_uuid="u-1", administration_mode="01",
                                  submitted_at=timezone.now(), raw_payload_ref="x", payload_content_hash="h")
    started_and_submitted = _case(organisation, stratum, "S07")
    QUANSubmission.objects.create(sample_case=started_and_submitted, kobo_submission_uuid="u-2", administration_mode="01",
                                  submitted_at=timezone.now(), raw_payload_ref="y", payload_content_hash="h2")
    refused = _case(organisation, stratum, "S12")
    unverified = _case(organisation, stratum, "S00")
    waiting = _case(organisation, stratum, "S03")
    SampleCase.objects.filter(pk=activated_reserve_case.pk).update(workflow_status="S05")  # a Reserve is never reset here
    _run("--apply")
    for case in moving.values():
        case.refresh_from_db()
        assert case.workflow_status == "S03"
        assert not case.invitation_tokens.exclude(status__in=[TokenStatus.REVOKED, TokenStatus.EXPIRED]).exists()
    for case, status in ((completed, "S10"), (started_and_submitted, "S07"), (refused, "S12"), (unverified, "S00"), (waiting, "S03")):
        case.refresh_from_db()
        assert case.workflow_status == status, case.sample_id
    assert completed.invitation_tokens.exclude(status=TokenStatus.REVOKED).exists()  # a completed case keeps its link
    activated_reserve_case.refresh_from_db()
    assert activated_reserve_case.workflow_status == "S05"
    events = AuditEvent.objects.filter(action="sampling.status_reset_fresh_start")
    assert events.count() == 4 and {e.metadata["from"] for e in events} == {"S05", "S06", "S07", "S13"}
    assert all(e.metadata["reason"] == REASON for e in events)


def test_no_old_reminder_goes_out_after_the_reset(organisation, stratum, settings):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_SMS_FROM = "ACtest", "t", "CUT"
    case = _case(organisation, stratum, "S05")
    InvitationToken.objects.filter(sample_case=case).update(issued_at=timezone.now() - timezone.timedelta(days=2))
    _run("--apply")
    assert dispatch_due_reminders() == []


def test_consent_and_respondents_are_kept(organisation, stratum):
    gave = _case(organisation, stratum, "S07")
    declined = _case(organisation, stratum, "S06")
    for case, decision in ((gave, "GIVEN"), (declined, "DECLINED")):
        ConsentRecord.objects.create(sample_case=case, consent_type="PARTICIPATION", decision=decision, method="WEB_CLICKTHROUGH", timestamp=timezone.now())
    _run("--apply")
    assert ConsentRecord.objects.filter(sample_case__in=[gave, declined]).count() == 2
    assert Respondent.objects.filter(sample_case__in=[gave, declined]).count() == 2


def test_a_dry_run_changes_nothing_and_a_second_run_does_nothing(organisation, stratum):
    case = _case(organisation, stratum, "S05")
    out = _run()
    assert "1 cases would return to S03" in out and "Dry run" in out
    case.refresh_from_db()
    assert case.workflow_status == "S05" and not AuditEvent.objects.filter(action="sampling.status_reset_fresh_start").exists()
    _run("--apply")
    assert "0 cases would return" in _run("--apply")
    assert AuditEvent.objects.filter(action="sampling.status_reset_fresh_start").count() == 1


def test_a_reset_case_can_be_asked_first(organisation, stratum):
    from apps.messaging.outreach import introduction_candidates

    case = _case(organisation, stratum, "S06")
    assert not introduction_candidates().filter(pk=case.pk).exists()
    _run("--apply")
    assert introduction_candidates().filter(pk=case.pk).exists()


def test_a_reason_is_required():
    with pytest.raises(CommandError):
        call_command("fresh_start_outreach", "--reason", "x", stdout=StringIO())
