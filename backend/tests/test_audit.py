"""
apps.audit.middleware.AuditContextMiddleware attribution
(docs/18_DATA_PRIVACY_AND_COMPLIANCE.md: every AuditEvent must record who
performed the action). Confirmed hardening-pass bug: the middleware read
request.user at __call__ entry, before DRF's JWTAuthentication ran during
view dispatch, so it only ever saw the pre-auth value -- every AuditEvent
in the system was attributed to no one (rendered "system" in the admin UI)
regardless of which admin was actually signed in.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.sampling.models import ActivationReason, ReserveStatus


@pytest.fixture
def admin_user(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    return User.objects.create_user(username="audit_admin", password="testpass123", role=role)


@pytest.fixture
def auth_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


def test_audit_event_attributes_the_authenticated_caller_not_system(auth_client, admin_user, locked_reserve_case):
    """Goes through APIClient (the full Django middleware stack, including
    AuditContextMiddleware) rather than calling services directly, since the
    bug only manifested at the middleware/request layer."""
    url = f"/api/v1/sample-cases/{locked_reserve_case.sample_id}/activate-reserve/"
    response = auth_client.post(url, {
        "activation_reason": ActivationReason.NONRESPONSE_EXHAUSTED,
        "activation_evidence_note": "Audit attribution regression test.",
    })
    assert response.status_code == 200
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.ACTIVATED

    event = AuditEvent.objects.get(action="reserve.activated")
    assert event.user_id == admin_user.id
    assert event.user_id is not None


def test_the_audit_log_api_returns_a_readable_label_and_detail_alongside_the_raw_action(auth_client):
    from apps.audit.utils import log_action
    from apps.evidence.models import DocumentRecord
    from apps.evidence.services import generate_document_id

    doc = DocumentRecord.objects.create(document_id=generate_document_id(), title="x", document_type="OTHER")
    log_action("sampling.status_reset_after_test_cleanup", doc, {"from": "S07", "to": "S03"})

    response = auth_client.get("/api/v1/audit/?action=sampling.status_reset_after_test_cleanup")
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["action"] == "sampling.status_reset_after_test_cleanup"
    assert row["label"] == "Case status reset (test cleanup)"
    assert row["detail"] == "S07 → S03"
    assert row["metadata"] == {"from": "S07", "to": "S03"}
