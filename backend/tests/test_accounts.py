"""
Self-service password change and the Contact RA list used by the sample
case detail page's "Assigned RA" dropdown. Neither existed before -- password
rotation required Django admin or a server-shell script.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


@pytest.fixture
def user_and_client(db):
    role, _ = Role.objects.get_or_create(name=Role.FIELD_COORDINATOR)
    user = User.objects.create_user(username="password_test_user", password="OldPassword123!", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


def test_change_password_succeeds_with_correct_current_password(user_and_client):
    user, client = user_and_client
    resp = client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "OldPassword123!", "new_password": "BrandNewPassword456!"},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("BrandNewPassword456!")
    assert not user.check_password("OldPassword123!")


def test_change_password_rejects_wrong_current_password(user_and_client):
    user, client = user_and_client
    resp = client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "NotTheRealPassword", "new_password": "BrandNewPassword456!"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "invalid_current_password"
    user.refresh_from_db()
    assert user.check_password("OldPassword123!")


def test_change_password_rejects_weak_new_password(user_and_client):
    """Django's own AUTH_PASSWORD_VALIDATORS apply -- no bypass here."""
    user, client = user_and_client
    resp = client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "OldPassword123!", "new_password": "12345"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "invalid_new_password"
    user.refresh_from_db()
    assert user.check_password("OldPassword123!")


def test_change_password_requires_authentication():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "x", "new_password": "y"},
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_contact_ra_list_returns_only_contact_ra_users(db):
    admin_role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    contact_role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    admin_user = User.objects.create_user(username="cra_list_admin", password="testpass123", role=admin_role)
    User.objects.create_user(username="cra_one", password="testpass123", role=contact_role)
    User.objects.create_user(username="cra_two", password="testpass123", role=contact_role)

    client = APIClient()
    client.force_authenticate(user=admin_user)
    resp = client.get("/api/v1/auth/contact-ras/")
    assert resp.status_code == 200
    usernames = {r["username"] for r in resp.data["results"]}
    assert usernames == {"cra_one", "cra_two"}
    assert "cra_list_admin" not in usernames
