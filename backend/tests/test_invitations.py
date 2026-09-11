"""
Invitation token lifecycle -- docs/22_TESTING_STRATEGY.md: "generation
entropy/format, hashing (raw token never persisted), expiry, single-valid-
token supersession, revocation, rate limiting."
"""

import pytest
from django.utils import timezone

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
