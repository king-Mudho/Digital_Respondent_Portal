"""
docs/22_TESTING_STRATEGY.md: "explicitly assert every dashboard/aggregate
endpoint response never contains Organisation.name, Respondent.full_name,
or unbanded amounts." Plus reserve-activation integrity
(docs/28_DEFINITION_OF_DONE.md: audited, requires an authorised reason).
"""

import json

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.sampling.models import ActivationReason, ReserveStatus


@pytest.fixture
def admin_user(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="admin", password="testpass123", role=role)
    return user


@pytest.fixture
def auth_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


DASHBOARD_URLS = [
    "/api/v1/dashboards/executive/",
    "/api/v1/dashboards/sampling/",
    "/api/v1/dashboards/contact/",
    "/api/v1/dashboards/qa/",
    "/api/v1/dashboards/kii-documents/",
    "/api/v1/dashboards/cost/",
]


@pytest.mark.parametrize("url", DASHBOARD_URLS)
def test_dashboard_never_exposes_identifying_fields(auth_client, url, main_case):
    response = auth_client.get(url)
    assert response.status_code == 200
    body = json.dumps(response.json())
    assert main_case.organisation.name not in body
    assert "full_name" not in body
    assert "Test Organisation" not in body


def test_all_dashboards_return_200_for_admin(auth_client, main_case):
    for url in DASHBOARD_URLS:
        response = auth_client.get(url)
        assert response.status_code == 200, url


def test_dashboards_reject_unauthenticated(main_case):
    client = APIClient()
    for url in DASHBOARD_URLS:
        response = client.get(url)
        assert response.status_code in (401, 403), url


# --- Reserve activation ------------------------------------------------------

def test_reserve_activation_requires_authorised_reason(auth_client, locked_reserve_case):
    url = f"/api/v1/sample-cases/{locked_reserve_case.sample_id}/activate-reserve/"
    response = auth_client.post(url, {"activation_reason": "NOT_A_REAL_REASON"})
    assert response.status_code == 400
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.LOCKED


def test_reserve_activation_succeeds_and_is_audited(auth_client, admin_user, locked_reserve_case):
    from apps.audit.models import AuditEvent

    url = f"/api/v1/sample-cases/{locked_reserve_case.sample_id}/activate-reserve/"
    response = auth_client.post(url, {
        "activation_reason": ActivationReason.NONRESPONSE_EXHAUSTED,
        "activation_evidence_note": "Main case exhausted the Day 0/2/4-5/7 sequence with no contact.",
    })
    assert response.status_code == 200

    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.ACTIVATED
    assert locked_reserve_case.activated_by_id == admin_user.id
    assert locked_reserve_case.activated_at is not None
    event = AuditEvent.objects.get(action="reserve.activated")
    # Regression: apps.audit.middleware.AuditContextMiddleware used to read
    # request.user at middleware entry, before DRF's JWTAuthentication ran
    # during view dispatch -- every AuditEvent was attributed to no one
    # (None -> rendered "system" in the UI) regardless of who was signed in.
    assert event.user_id == admin_user.id


def test_activated_reserve_can_now_be_invited(auth_client, locked_reserve_case):
    from apps.invitations.services import issue_invitation

    url = f"/api/v1/sample-cases/{locked_reserve_case.sample_id}/activate-reserve/"
    auth_client.post(url, {"activation_reason": ActivationReason.REFUSAL})

    locked_reserve_case.refresh_from_db()
    raw_token, _, _ = issue_invitation(locked_reserve_case)
    assert raw_token
