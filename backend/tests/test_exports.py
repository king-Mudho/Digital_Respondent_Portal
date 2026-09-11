"""
docs/28_DEFINITION_OF_DONE.md: "the de-identified analysis export and the
full operational export both work and have the documented schema
difference (contact fields present only in the operational export)."
docs/22_TESTING_STRATEGY.md privacy assertions extend to exports too.
"""

import csv
import io

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent, RoleCategory
from apps.kobo.models import AdministrationMode, QAStatus, QUANSubmission
from django.utils import timezone


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="admin2", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def submission_with_respondent(main_case):
    Respondent.objects.create(
        sample_case=main_case,
        full_name="Jane Doe",
        role_category=RoleCategory.CEO_MD,
        phone="+263771111111",
        email="jane@example.com",
        gatekeeper_name="Gatekeeper Smith",
    )
    return QUANSubmission.objects.create(
        sample_case=main_case,
        kobo_submission_uuid="export-test-uuid",
        administration_mode=AdministrationMode.WEB_SELF,
        submitted_at=timezone.now(),
        qa_status=QAStatus.QA_PASSED,
        completion_seconds=900,
    )


def _parse_csv(content: bytes):
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"))))


def test_analysis_export_excludes_contact_fields(admin_client, submission_with_respondent):
    response = admin_client.get("/api/v1/export/analysis/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")

    assert "Jane Doe" not in body
    assert "jane@example.com" not in body
    assert "+263771111111" not in body
    assert "Gatekeeper Smith" not in body
    assert "Test Organisation" not in body  # organisation name also excluded

    rows = _parse_csv(response.content)
    assert rows[0]["sample_id"] == submission_with_respondent.sample_case.sample_id
    assert "respondent_full_name" not in rows[0]


def test_operational_export_includes_contact_fields(admin_client, submission_with_respondent):
    response = admin_client.get("/api/v1/export/operational/")
    assert response.status_code == 200
    rows = _parse_csv(response.content)

    assert rows[0]["respondent_full_name"] == "Jane Doe"
    assert rows[0]["organisation_name"] == "Test Organisation"
    assert rows[0]["respondent_email"] == "jane@example.com"


def test_analysis_export_forbidden_for_ra_without_analyst_role(db, submission_with_respondent):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="contactra", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/export/analysis/")
    assert response.status_code == 403


def test_operational_export_forbidden_for_analyst(db, submission_with_respondent):
    """Operational export (with contact data) is IsAdminOnly -- an Analyst
    gets the de-identified export only, never the operational one."""
    role, _ = Role.objects.get_or_create(name=Role.ANALYST)
    user = User.objects.create_user(username="analyst1", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/export/operational/")
    assert response.status_code == 403


def test_qa_decision_is_audited(admin_client, submission_with_respondent):
    from apps.audit.models import AuditEvent

    response = admin_client.post(
        f"/api/v1/qa/submission/{submission_with_respondent.id}/decision/",
        {"decision": "ACCEPT", "note": "Reviewed and looks correct."},
        format="json",
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(action="qa.decision").exists()
