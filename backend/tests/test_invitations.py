"""
Invitation token lifecycle -- docs/22_TESTING_STRATEGY.md: "generation
entropy/format, hashing (raw token never persisted), expiry, single-valid-
token supersession, revocation, rate limiting."
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.invitations.models import TokenStatus
from apps.invitations.services import (
    TokenNotInvitable,
    TokenValidationError,
    issue_invitation,
    revoke_token,
    validate_manual_code,
    validate_token,
)


def test_issue_invitation_returns_valid_token(main_case):
    raw_token, raw_code, token = issue_invitation(main_case)
    assert len(raw_token) > 32  # 32 bytes base64url-encoded
    resolved = validate_token(raw_token)
    assert resolved.pk == token.pk


def test_raw_token_never_persisted(main_case):
    raw_token, _, token = issue_invitation(main_case)
    assert raw_token not in token.token_hash
    assert "$" in token.token_hash  # salt$digest


def test_manual_code_also_validates(main_case):
    _, raw_code, token = issue_invitation(main_case)
    resolved = validate_manual_code(raw_code)
    assert resolved.pk == token.pk


def test_wrong_token_is_rejected(main_case):
    issue_invitation(main_case)
    with pytest.raises(TokenValidationError) as exc_info:
        validate_token("not-a-real-token")
    assert exc_info.value.code == "token_invalid"


def test_issuing_new_token_supersedes_prior(main_case):
    raw_token_1, _, token_1 = issue_invitation(main_case)
    raw_token_2, _, token_2 = issue_invitation(main_case, invitation_wave=2)

    token_1.refresh_from_db()
    assert token_1.status == TokenStatus.EXPIRED

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token_1)
    assert exc_info.value.code in ("token_invalid", "token_expired")

    resolved = validate_token(raw_token_2)
    assert resolved.pk == token_2.pk


def test_expired_token_rejected(main_case):
    raw_token, _, token = issue_invitation(main_case)
    token.expires_at = timezone.now() - timezone.timedelta(days=1)
    token.save(update_fields=["expires_at"])

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token)
    assert exc_info.value.code == "token_expired"


def test_revoked_token_rejected(main_case):
    raw_token, _, token = issue_invitation(main_case)
    revoke_token(token, "respondent requested revocation")

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token)
    assert exc_info.value.code == "token_revoked"


# --- Reserve lock enforcement at the invitation boundary --------------------

def test_cannot_issue_invitation_for_locked_reserve(locked_reserve_case):
    with pytest.raises(TokenNotInvitable):
        issue_invitation(locked_reserve_case)


def test_can_issue_invitation_for_activated_reserve(activated_reserve_case):
    raw_token, _, token = issue_invitation(activated_reserve_case)
    resolved = validate_token(raw_token)
    assert resolved.pk == token.pk


# --- API: the "Send Invitation" panel's backing endpoints -------------------

@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="invite_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_issue_endpoint_returns_raw_token_once(admin_client, main_case):
    resp = admin_client.post(
        "/api/v1/invitations/", {"sample_id": main_case.sample_id, "channel": "WHATSAPP", "invitation_wave": 1},
        format="json",
    )
    assert resp.status_code == 201
    assert len(resp.data["raw_token"]) > 32
    assert resp.data["raw_manual_code"]


def test_issue_endpoint_rejects_locked_reserve(admin_client, locked_reserve_case):
    resp = admin_client.post(
        "/api/v1/invitations/", {"sample_id": locked_reserve_case.sample_id, "channel": "WHATSAPP"}, format="json",
    )
    assert resp.status_code == 403
    assert resp.data["error"]["code"] == "not_invitable"


def test_list_endpoint_never_exposes_the_raw_token_or_its_hash(admin_client, main_case):
    issue_invitation(main_case)
    resp = admin_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    entry = resp.data["results"][0]
    assert "token_hash" not in entry
    assert "manual_code_hash" not in entry
    assert entry["status"] == TokenStatus.GENERATED
    assert entry["channel"] == "WHATSAPP"


def test_list_endpoint_requires_sample_id(admin_client):
    resp = admin_client.get("/api/v1/invitations/")
    assert resp.status_code == 400


def test_list_endpoint_orders_newest_first_after_supersession(admin_client, main_case):
    issue_invitation(main_case, invitation_wave=1)
    issue_invitation(main_case, invitation_wave=2)
    resp = admin_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}")
    results = resp.data["results"]
    assert len(results) == 2
    assert results[0]["invitation_wave"] == 2
    assert results[0]["status"] == TokenStatus.GENERATED
    assert results[1]["invitation_wave"] == 1
    assert results[1]["status"] == TokenStatus.EXPIRED


def test_revoke_endpoint_marks_token_revoked(admin_client, main_case):
    _, _, token = issue_invitation(main_case)
    resp = admin_client.post(f"/api/v1/invitations/{token.id}/revoke/", {"reason": "Issued in error"}, format="json")
    assert resp.status_code == 200
    token.refresh_from_db()
    assert token.status == TokenStatus.REVOKED
    assert token.revoked_reason == "Issued in error"
