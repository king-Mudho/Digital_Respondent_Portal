"""
Hardening pass (Sep 2026): a real bug was found here -- PATCHing
/api/v1/sample-cases/{id}/ with an arbitrary workflow_status silently
succeeded and bypassed the S00-S16 state machine entirely (no validation,
no AuditEvent), letting a case jump straight from S00 to S11. Fixed by
making status/workflow_status/activation_* read-only on the serializer and
adding a dedicated, validated /transition/ endpoint. These tests both
reproduce the original bug (as a regression guard) and confirm the fix.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.sampling.models import WorkflowStatus


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="sc_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_patch_no_longer_changes_workflow_status(admin_client, main_case):
    resp = admin_client.patch(
        f"/api/v1/sample-cases/{main_case.sample_id}/",
        {"workflow_status": WorkflowStatus.S11_COMPLETED},
        format="json",
    )
    assert resp.status_code == 200  # PATCH still succeeds -- it just ignores the read-only field
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S00_SELECTED_MAIN  # unchanged


def test_patch_no_longer_changes_reserve_activation_fields(admin_client, locked_reserve_case):
    resp = admin_client.patch(
        f"/api/v1/sample-cases/{locked_reserve_case.sample_id}/",
        {"activation_reason": "REFUSAL", "status": "ACTIVATED"},
        format="json",
    )
    assert resp.status_code == 200
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == "LOCKED"  # unchanged -- must go through activate-reserve/
    assert locked_reserve_case.activation_reason is None


def test_transition_endpoint_applies_a_valid_transition(admin_client, main_case):
    resp = admin_client.post(
        f"/api/v1/sample-cases/{main_case.sample_id}/transition/",
        {"workflow_status": WorkflowStatus.S01_VERIFICATION_REQUIRED},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["workflow_status"] == WorkflowStatus.S01_VERIFICATION_REQUIRED
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S01_VERIFICATION_REQUIRED


def test_transition_endpoint_rejects_invalid_transition_and_audits_it(admin_client, main_case):
    resp = admin_client.post(
        f"/api/v1/sample-cases/{main_case.sample_id}/transition/",
        {"workflow_status": WorkflowStatus.S11_COMPLETED},  # S00 -> S11 skips everything
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "invalid_transition"
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S00_SELECTED_MAIN  # unchanged
    assert AuditEvent.objects.filter(action="sampling.invalid_workflow_transition").exists()


def test_transition_endpoint_requires_field_coordinator_or_admin(main_case):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="ra_only", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.post(
        f"/api/v1/sample-cases/{main_case.sample_id}/transition/",
        {"workflow_status": WorkflowStatus.S01_VERIFICATION_REQUIRED},
        format="json",
    )
    assert resp.status_code == 403
