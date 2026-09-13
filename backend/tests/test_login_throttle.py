"""
Internal sign-in has its own throttle bucket.

Found during the end-to-end audit pass: /auth/token/ used DRF's default
throttles, so it shared the generic "anon" allowance with every public
respondent endpoint. A research team behind one office NAT is a single IP,
so ordinary staff sign-ins competed with respondent token validation for
the same 30/minute -- and the resulting 429 reached the login screen as
"Invalid username or password".
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from api.throttling import LoginRateThrottle, PerTokenThrottle
from apps.accounts.models import Role, User


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Throttle state lives in the cache and would leak between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    return User.objects.create_user(username="throttle_user", password="testpass123", role=role)


def test_login_uses_its_own_throttle_scope_not_the_shared_anon_one():
    from apps.accounts.views import InternalTokenObtainView

    scopes = {t.scope for t in InternalTokenObtainView.throttle_classes}

    assert scopes == {"login"}
    assert "anon" not in scopes, "sign-in must not share the respondent endpoints' bucket"


def test_respondent_traffic_does_not_consume_the_login_allowance(user):
    """The actual regression: hitting the anon bucket must leave sign-in
    alone. Exhaust the respondent-facing allowance, then sign in."""
    # Fill the shared anon bucket the public endpoints use.
    anon_client = APIClient()
    for _ in range(35):
        anon_client.get("/api/v1/invitations/validate/?t=not-a-real-token")

    response = APIClient().post(
        "/api/v1/auth/token/", {"username": "throttle_user", "password": "testpass123"}, format="json"
    )

    assert response.status_code == 200, "sign-in was throttled by respondent traffic"
    assert "access" in response.json()


def test_login_is_still_throttled_against_password_guessing(user):
    """Isolating the bucket must not remove the brute-force limit."""
    client = APIClient()
    rate = LoginRateThrottle().num_requests

    statuses = [
        client.post(
            "/api/v1/auth/token/", {"username": "throttle_user", "password": "wrong"}, format="json"
        ).status_code
        for _ in range(rate + 3)
    ]

    assert 429 in statuses, "sign-in has no rate limit at all"
    assert statuses[0] == 401, "the first attempt should fail on credentials, not throttling"


def test_per_token_throttle_still_covers_the_respondent_endpoints():
    """The login change must not have disturbed the token-guessing limit
    (docs/10_INVITATION_AND_CONSENT.md)."""
    assert PerTokenThrottle.scope == "invitation_token"
