"""
A case's S00-S16 workflow status follows its respondent.

Until 2026-09-14 a case reached S05 when invited and never moved again:
opening the link, starting the questionnaire, submitting it and passing QA
all advanced the invitation token's funnel but not the case. The reminder
sequence targets cases at S04-S06, so a respondent who had already submitted
would still have been chased, and the Main-400 register showed "Invitation
sent" for every case in the study.
"""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.services import record_eligibility_check
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation, validate_token
from apps.kobo.models import QUANSubmission, ReconciliationTrigger
from apps.kobo.services import reconcile
from apps.qa.models import QADecision
from apps.qa.services import record_human_decision
from apps.sampling.models import WorkflowStatus
from apps.sampling.services import (
    advance_case_on_qa_outcome,
    advance_case_on_respondent_event,
    transition_workflow_status,
)


@pytest.fixture(autouse=True)
def connected_kobo(settings):
    settings.KOBO_ASSET_UID = "test-asset-uid"
    settings.KOBO_API_TOKEN = "test-api-token"
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/TeStFoRm"


def _verified(case):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    return case


def _status(case):
    case.refresh_from_db()
    return case.workflow_status


def _payload(sample_id):
    return {
        "_uuid": "wf-uuid", "_submitted_by": "enumerator1", "sample_id": sample_id, "administration_mode": "01",
        "start": "2026-09-14T08:00:00+00:00", "end": "2026-09-14T08:20:00+00:00",
        "_submission_time": "2026-09-14T08:20:05",
    }


@pytest.mark.django_db
def test_a_case_follows_its_respondent_from_invitation_to_qa_passed(main_case):
    _verified(main_case)
    raw_token, _, token = issue_invitation(main_case)
    assert _status(main_case) == WorkflowStatus.S05_INVITATION_SENT

    validate_token(raw_token)
    assert _status(main_case) == WorkflowStatus.S06_INVITATION_OPENED

    record_eligibility_check(sample_case=main_case, full_name="Tendai Moyo", role_category="CEO_MD", is_eligible=True)
    record_consent(
        sample_case=main_case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.2", method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    resp = APIClient().get(f"/api/v1/kobo/redirect-url/?t={raw_token}&administration_mode=01")
    assert resp.status_code == 200
    assert _status(main_case) == WorkflowStatus.S07_SURVEY_STARTED
    token.refresh_from_db()
    assert token.status == TokenStatus.SURVEY_STARTED

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_payload(main_case.sample_id)]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    assert _status(main_case) == WorkflowStatus.S08_SURVEY_SUBMITTED

    role, _ = Role.objects.get_or_create(name=Role.QUAN_QA_RA)
    reviewer = User.objects.create_user(username="wf_qa", password="x", role=role)
    record_human_decision(
        submission=QUANSubmission.objects.get(), reviewer=reviewer, decision=QADecision.ACCEPT, note="Checked.",
    )
    assert _status(main_case) == WorkflowStatus.S10_QA_PASSED


@pytest.mark.django_db
def test_a_collect_submission_walks_a_case_through_the_steps_it_skipped(main_case):
    _verified(main_case)
    issue_invitation(main_case)

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_payload(main_case.sample_id)]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert _status(main_case) == WorkflowStatus.S08_SURVEY_SUBMITTED


@pytest.mark.django_db
def test_verification_is_never_inferred_from_respondent_activity(main_case):
    """An invitation issued before the case was verified (S00) does not
    walk the case through S01-S03 -- those are a researcher's decisions."""
    raw_token, _, _ = issue_invitation(main_case)
    validate_token(raw_token)

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_payload(main_case.sample_id)]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert _status(main_case) == WorkflowStatus.S00_SELECTED_MAIN
    assert InvitationToken.objects.get().status == TokenStatus.SUBMITTED  # the funnel still records it


@pytest.mark.django_db
def test_status_never_moves_backwards(main_case):
    _verified(main_case)
    issue_invitation(main_case)
    advance_case_on_respondent_event(main_case, WorkflowStatus.S08_SURVEY_SUBMITTED)

    advance_case_on_respondent_event(main_case, WorkflowStatus.S06_INVITATION_OPENED)  # a revisit
    assert _status(main_case) == WorkflowStatus.S08_SURVEY_SUBMITTED

    advance_case_on_qa_outcome(main_case, passed=True)
    advance_case_on_qa_outcome(main_case, passed=False)  # a later edit re-queried in QA
    assert _status(main_case) == WorkflowStatus.S10_QA_PASSED


@pytest.mark.django_db
def test_an_automated_qa_flag_moves_a_submitted_case_to_query(main_case):
    from apps.qa.services import seed_default_thresholds

    seed_default_thresholds()
    _verified(main_case)
    issue_invitation(main_case)
    too_quick = dict(_payload(main_case.sample_id), end="2026-09-14T08:02:00+00:00")

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[too_quick]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert _status(main_case) == WorkflowStatus.S09_QA_QUERY


# --- Bulk verification steps -------------------------------------------------

def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


@pytest.mark.django_db
def test_a_coordinator_moves_every_case_at_a_step_forward_at_once(organisation, stratum):
    from apps.audit.models import AuditEvent
    from apps.sampling.models import SampleCase, SampleType
    from apps.sampling.services import create_sample_case

    cases = [create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026) for _ in range(3)]
    transition_workflow_status(cases[2], "S01")
    fc = _client(Role.FIELD_COORDINATOR, "bulk_fc")

    resp = fc.post("/api/v1/sample-cases/bulk-transition/", {"from_status": "S00"}, format="json")

    assert resp.status_code == 200 and resp.json()["moved"] == 2
    assert set(SampleCase.objects.values_list("workflow_status", flat=True)) == {"S01"}
    assert AuditEvent.objects.filter(action="sampling.bulk_workflow_transition").count() == 1

    resp = fc.post("/api/v1/sample-cases/bulk-transition/", {"from_status": "S01", "sample_ids": [cases[0].sample_id]}, format="json")
    assert resp.json()["sample_ids"] == [cases[0].sample_id]


@pytest.mark.django_db
def test_bulk_changes_stop_at_s03_and_need_a_coordinator(main_case):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(main_case, status)
    fc = _client(Role.FIELD_COORDINATOR, "bulk_fc2")

    assert fc.post("/api/v1/sample-cases/bulk-transition/", {"from_status": "S03"}, format="json").status_code == 400
    ra = _client(Role.CONTACT_RA, "bulk_ra")
    assert ra.post("/api/v1/sample-cases/bulk-transition/", {"from_status": "S00"}, format="json").status_code == 403


# --- Verified later: the status catches up (2026-10-12) ---------------------------------------------------------------
# On production 23 hand-registered cases were invited at S00, then bulk-verified to S03, and sat at S03 holding sent,
# opened and QA-passed links: miscounted, and offered to batches and introductions again.

def _respond(case, *, upto):
    raw_token, _, token = issue_invitation(case)
    validate_token(raw_token)
    InvitationToken.objects.filter(pk=token.pk).update(status=upto)
    return token


@pytest.mark.django_db
def test_verifying_an_already_invited_case_brings_its_status_up_to_its_respondent(main_case):
    _respond(main_case, upto=TokenStatus.SURVEY_STARTED)
    assert _status(main_case) == WorkflowStatus.S00_SELECTED_MAIN  # still never inferred before verification
    _verified(main_case)
    assert _status(main_case) == WorkflowStatus.S07_SURVEY_STARTED
    from apps.audit.models import AuditEvent

    event = AuditEvent.objects.get(action="sampling.status_caught_up")
    assert (event.metadata["from"], event.metadata["to"]) == ("S03", "S07")


@pytest.mark.django_db
def test_a_qa_passed_respondent_lands_on_qa_passed_when_verified(main_case):
    _respond(main_case, upto=TokenStatus.QA_PASSED)
    _verified(main_case)
    assert _status(main_case) == WorkflowStatus.S10_QA_PASSED


@pytest.mark.django_db
def test_bulk_verification_catches_up_too(main_case):
    from apps.sampling.services import bulk_transition_workflow_status

    _respond(main_case, upto=TokenStatus.SENT)
    for status in ("S00", "S01", "S02"):
        bulk_transition_workflow_status(from_status=status)
    assert _status(main_case) == WorkflowStatus.S05_INVITATION_SENT


@pytest.mark.django_db
def test_a_revoked_link_alone_moves_nothing(main_case):
    _respond(main_case, upto=TokenStatus.REVOKED)
    _verified(main_case)
    assert _status(main_case) == WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED


@pytest.mark.django_db
def test_a_respondent_who_submitted_is_never_offered_for_contact_again(main_case):
    from apps.contacts.models import Respondent
    from apps.invitations.batch import batch_candidates
    from apps.sampling.models import SampleCase
    from apps.sampling.services import contactable_cases

    _verified(main_case)
    Respondent.objects.create(sample_case=main_case, full_name="Jane", phone="0771234567", email="j@x.example")
    token = _respond(main_case, upto=TokenStatus.SUBMITTED)
    # Whatever put the status back at S03, a completed respondent stays out of every contact list.
    SampleCase.objects.filter(pk=main_case.pk).update(workflow_status="S03", status="S03")
    assert token.sample_case_id == main_case.pk
    assert not contactable_cases().filter(pk=main_case.pk).exists()
    assert not batch_candidates(("EMAIL", "WHATSAPP")).filter(pk=main_case.pk).exists()


@pytest.mark.django_db
def test_the_repair_command_lists_then_applies_and_leaves_unverified_cases_alone(main_case, organisation, stratum):
    from io import StringIO

    from django.core.management import call_command

    from apps.sampling.models import SampleCase
    from apps.sampling.services import create_sample_case

    _respond(main_case, upto=TokenStatus.OPENED)
    SampleCase.objects.filter(pk=main_case.pk).update(workflow_status="S03", status="S03")  # as found on production
    unverified = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    _respond(unverified, upto=TokenStatus.QA_PASSED)
    out = StringIO()
    call_command("catch_up_case_status", stdout=out)
    assert "S03 -> S06" in out.getvalue() and _status(main_case) == "S03"  # a dry run changes nothing
    assert unverified.sample_id in out.getvalue()
    call_command("catch_up_case_status", "--apply", stdout=StringIO())
    assert _status(main_case) == "S06" and _status(unverified) == "S00"
