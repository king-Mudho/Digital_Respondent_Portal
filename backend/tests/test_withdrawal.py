"""
Recording a withdrawal (docs/10, docs/18). Until 2026-09-14 nothing could
record one: no staff screen or endpoint existed, so a participant who phoned
to withdraw kept a live link and stayed in the reminder queue.
"""

import csv
import io
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import has_given_consent, latest_consent, record_consent
from apps.contacts.models import Respondent
from apps.invitations.models import TokenStatus
from apps.invitations.services import issue_invitation
from apps.kobo.models import ReconciliationTrigger
from apps.kobo.services import reconcile
from apps.messaging.services import due_follow_ups
from apps.sampling.models import WorkflowStatus
from apps.sampling.services import transition_workflow_status


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _consented_case(case):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    Respondent.objects.create(
        sample_case=case, full_name="Tendai Moyo", is_eligible=True, phone="0771234567",
        whatsapp_number="0771234567", email="t@example.org", gatekeeper_contact="0242 000000",
    )
    issue_invitation(case)
    record_consent(
        sample_case=case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.2", method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    return case


@pytest.mark.django_db
def test_withdrawal_before_submission(main_case):
    _consented_case(main_case)
    token = main_case.invitation_tokens.get(status__in=[TokenStatus.SENT, TokenStatus.GENERATED])
    token.issued_at = timezone.now() - timedelta(days=3)
    token.save(update_fields=["issued_at"])
    assert due_follow_ups()  # was being chased

    resp = _client(Role.FIELD_COORDINATOR, "wd_fc").post(
        f"/api/v1/sample-cases/{main_case.sample_id}/withdraw/", {"reason": "Phoned to withdraw"}, format="json",
    )

    assert resp.status_code == 201, resp.json()
    assert not has_given_consent(main_case)
    record = latest_consent(main_case, ConsentType.PARTICIPATION)
    assert (record.decision, record.information_sheet_version) == (ConsentDecision.WITHDRAWN, "v1.2")
    token.refresh_from_db()
    assert token.status == TokenStatus.REVOKED
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S12_REFUSED
    respondent = main_case.respondents.get()
    assert (respondent.phone, respondent.whatsapp_number, respondent.email, respondent.gatekeeper_contact) == ("", "", "", "")
    assert due_follow_ups() == []
    assert AuditEvent.objects.filter(action="consent.withdrawal_processed").exists()


@pytest.mark.django_db
def test_withdrawal_after_submission_keeps_status_and_flags_the_export(main_case, settings):
    settings.KOBO_ASSET_UID, settings.KOBO_API_TOKEN = "asset", "token"
    _consented_case(main_case)
    payload = {"_uuid": "wd-1", "_submitted_by": "enumerator1", "sample_id": main_case.sample_id, "administration_mode": "01",
               "start": "2026-09-14T08:00:00+00:00", "_submission_time": "2026-09-14T08:20:00"}
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    main_case.refresh_from_db()
    submitted_status = main_case.workflow_status

    _client(Role.PI_ADMIN, "wd_pi").post(
        f"/api/v1/sample-cases/{main_case.sample_id}/withdraw/", {"reason": "Asked for data not to be used"}, format="json",
    )

    main_case.refresh_from_db()
    assert main_case.workflow_status == submitted_status
    def rows(resp):
        body = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        return list(csv.DictReader(io.StringIO(body.decode())))

    # PI decision 15 Sep 2026: kept, but left out of analysis.
    assert rows(_client(Role.ANALYST, "wd_an").get("/api/v1/export/analysis/")) == []
    [row] = rows(_client(Role.PI_ADMIN, "wd_pi2").get("/api/v1/export/operational/"))
    assert row["consent_withdrawn"] == "True" and row["sample_id"] == main_case.sample_id


@pytest.mark.django_db
def test_withdrawal_needs_a_reason_a_coordinator_and_happens_once(main_case):
    _consented_case(main_case)
    url = f"/api/v1/sample-cases/{main_case.sample_id}/withdraw/"

    assert _client(Role.CONTACT_RA, "wd_ra").post(url, {"reason": "x"}, format="json").status_code == 403
    fc = _client(Role.FIELD_COORDINATOR, "wd_fc2")
    assert fc.post(url, {"reason": " "}, format="json").status_code == 400
    assert fc.post(url, {"reason": "Withdrew"}, format="json").status_code == 201
    assert fc.post(url, {"reason": "Again"}, format="json").status_code == 409
