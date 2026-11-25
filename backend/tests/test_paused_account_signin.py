"""A paused (deactivated) research assistant is told to contact the PI, not that the password is wrong (25 Nov 2026).

The PI deactivated the call RAs who weren't calling and asked that they contact him to be reactivated. Django refuses
an inactive account exactly like a wrong password, so they would have seen "Invalid username or password".
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def paused_ra(db):
    role, _ = Role.objects.get_or_create(name=Role.TELEPHONE_RA)
    return User.objects.create_user(username="paused_ra", password="right-pass-123", role=role, is_active=False)


def _sign_in(username, password):
    return APIClient().post("/api/v1/auth/token/", {"username": username, "password": password}, format="json")


def test_a_paused_account_with_its_right_password_is_told_to_contact_the_pi(paused_ra):
    resp = _sign_in("paused_ra", "right-pass-123")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "account_paused"
    assert "contact the PI" in resp.json()["error"]["message"]
    assert "access" not in resp.json() and "refresh" not in resp.json()


def test_a_wrong_password_on_a_paused_account_reveals_nothing(paused_ra):
    resp = _sign_in("paused_ra", "wrong-pass")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] != "account_paused"


def test_an_unknown_username_is_refused_as_before(db):
    resp = _sign_in("nobody_here", "whatever")
    assert resp.status_code == 401


def test_reactivated_account_signs_in(paused_ra):
    paused_ra.is_active = True
    paused_ra.save(update_fields=["is_active"])
    resp = _sign_in("paused_ra", "right-pass-123")
    assert resp.status_code == 200 and "access" in resp.json()
