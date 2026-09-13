"""
Every role's screen list, and the endpoints behind each screen, checked
role-by-role against docs/18's access matrix.

Why this file exists: the Research Operations Centre's nav bar used to
render all 14 links to all 8 roles. A Contact RA saw "Audit Log", "Export",
"QA Queue" and every dashboard, and got a 403 on click; four of the eight
roles also landed on /admin/dashboard at sign-in, a screen their own role is
refused. api/navigation.py is now the single source of truth for who sees
what, and these tests pin it to the permission classes that actually guard
the endpoints -- so the nav can't drift back into offering screens the API
refuses (or hiding ones it allows).
"""

import pytest
from rest_framework.test import APIClient

from api.navigation import SCREENS, can_open_path, landing_path_for_role, screens_for_role
from apps.accounts.models import Role, User

# role -> the exact set of screen ids that role should see, per docs/18.
EXPECTED_SCREENS = {
    Role.PI_ADMIN: set(SCREENS),  # everything
    Role.FIELD_COORDINATOR: {
        "dashboard_executive", "dashboard_sampling", "dashboard_contact", "dashboard_qa",
        "dashboard_kii_documents", "sample_register", "organisations", "appointments",
        "qa_queue", "kii_register", "documents", "reserve", "cost", "export",
    },
    Role.CONTACT_RA: {"sample_register", "appointments"},
    Role.QUAN_QA_RA: {"dashboard_qa", "qa_queue"},
    Role.KII_RA: {"dashboard_kii_documents", "kii_register"},
    Role.DOCUMENTARY_RA: {"dashboard_kii_documents", "documents"},
    Role.ANALYST: {
        "dashboard_executive", "dashboard_sampling", "dashboard_contact",
        "dashboard_kii_documents", "cost", "export",
    },
    Role.SUPERVISOR_READONLY: {
        "dashboard_executive", "dashboard_sampling", "dashboard_contact", "dashboard_qa",
        "dashboard_kii_documents", "sample_register", "organisations", "appointments",
        "qa_queue", "kii_register", "documents", "reserve", "cost",
    },
}


def client_for(role_name, username=None):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(
        username=username or f"nav_{role_name.lower()}", password="testpass123", role=role
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.user = user
    return client


@pytest.mark.parametrize("role_name,expected", sorted(EXPECTED_SCREENS.items()))
def test_role_sees_exactly_its_own_screens(db, role_name, expected):
    assert {s["id"] for s in screens_for_role(role_name)} == expected


@pytest.mark.parametrize("role_name,expected", sorted(EXPECTED_SCREENS.items()))
def test_me_endpoint_reports_that_same_screen_list(db, role_name, expected):
    resp = client_for(role_name).get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert {s["id"] for s in resp.data["screens"]} == expected
    assert resp.data["role"] == role_name


def test_no_role_lands_on_a_screen_it_cannot_open(db):
    """The old hardcoded /admin/dashboard landing broke Contact RA, QUAN QA
    RA, KII RA and Documentary RA -- all four were sent to a screen their
    own role is refused."""
    for role_name in EXPECTED_SCREENS:
        landing = landing_path_for_role(role_name)
        assert can_open_path(role_name, landing), f"{role_name} lands on a screen it cannot open"


def test_every_role_can_open_its_own_account_screen(db):
    for role_name in EXPECTED_SCREENS:
        assert can_open_path(role_name, "/admin/account")


def test_detail_routes_inherit_their_parent_screens_permission(db):
    # Contact RA works cases, so it may open a case detail page...
    assert can_open_path(Role.CONTACT_RA, "/admin/sample/SID-2026-000001")
    # ...but never a KII record or a document.
    assert not can_open_path(Role.CONTACT_RA, "/admin/kii/3")
    assert not can_open_path(Role.CONTACT_RA, "/admin/documents/3")
    # KII RA is the mirror image.
    assert can_open_path(Role.KII_RA, "/admin/kii/3")
    assert not can_open_path(Role.KII_RA, "/admin/sample/SID-2026-000001")


def test_unauthenticated_has_no_screens(db):
    assert screens_for_role(None) == []
    assert not can_open_path(None, "/admin/dashboard")


def test_me_endpoint_requires_authentication(db):
    assert APIClient().get("/api/v1/auth/me/").status_code in (401, 403)


def test_read_only_roles_are_flagged_as_such(db):
    for role_name in (Role.SUPERVISOR_READONLY, Role.ANALYST):
        assert client_for(role_name).get("/api/v1/auth/me/").data["read_only"] is True
    for role_name in (Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.CONTACT_RA):
        assert client_for(role_name).get("/api/v1/auth/me/").data["read_only"] is False


# --- The nav must match what the API actually allows ------------------------
# One representative endpoint per screen. If a role is offered the screen it
# must not get a 403 from the screen's own endpoint, and if it isn't offered
# the screen it must not be able to read that endpoint either.

SCREEN_ENDPOINTS = {
    "dashboard_executive": "/api/v1/dashboards/executive/",
    "dashboard_sampling": "/api/v1/dashboards/sampling/",
    "dashboard_contact": "/api/v1/dashboards/contact/",
    "dashboard_qa": "/api/v1/dashboards/qa/",
    "dashboard_kii_documents": "/api/v1/dashboards/kii-documents/",
    "sample_register": "/api/v1/sample-cases/",
    "organisations": "/api/v1/organisations/",
    "appointments": "/api/v1/appointments/",
    "qa_queue": "/api/v1/qa/queue/",
    "kii_register": "/api/v1/kii/",
    "documents": "/api/v1/documents/",
    "cost": "/api/v1/dashboards/cost/",
    "audit": "/api/v1/audit/",
    "export": "/api/v1/export/analysis/",
}


@pytest.mark.parametrize("role_name", sorted(EXPECTED_SCREENS))
def test_offered_screens_are_actually_reachable(db, role_name):
    client = client_for(role_name)
    for screen_id, url in SCREEN_ENDPOINTS.items():
        if screen_id not in EXPECTED_SCREENS[role_name]:
            continue
        assert client.get(url).status_code != 403, (
            f"{role_name} is offered {screen_id} in the nav but the API refuses {url}"
        )


# (role, screen) pairs the nav deliberately hides even though the API would
# allow a read. Each needs a reason -- this is not a place to silence
# failures, it's a place to be explicit that the nav is intentionally
# tighter than the permission class for a screen whose whole purpose is a
# write the role doesn't have.
NAV_TIGHTER_THAN_API = {
    # /admin/organisations is a "register a new organisation" form. Contact
    # RA can read organisation data (CanViewSampleCases allows GET, and it
    # already sees the same organisations through the Main-400 Register)
    # but never registers one, so the screen stays out of its nav.
    (Role.CONTACT_RA, "organisations"),
}


@pytest.mark.parametrize("role_name", sorted(EXPECTED_SCREENS))
def test_hidden_screens_are_actually_refused(db, role_name):
    """The nav hiding a screen has to mean something -- the endpoint behind
    it must refuse this role too, otherwise the nav is just cosmetic.
    NAV_TIGHTER_THAN_API lists the deliberate, reasoned exceptions."""
    client = client_for(role_name)
    for screen_id, url in SCREEN_ENDPOINTS.items():
        if screen_id in EXPECTED_SCREENS[role_name]:
            continue
        if (role_name, screen_id) in NAV_TIGHTER_THAN_API:
            continue
        assert client.get(url).status_code == 403, (
            f"{role_name} is not offered {screen_id} but can still read {url}"
        )


def test_contact_ra_cannot_create_an_organisation_even_though_it_can_read_one(db):
    """The reason /admin/organisations is hidden from Contact RA: it's a
    creation screen, and creation is refused."""
    client = client_for(Role.CONTACT_RA, username="nav_contact_ra_org")
    assert client.get("/api/v1/organisations/").status_code == 200
    assert client.post("/api/v1/organisations/", {"name": "X"}, format="json").status_code == 403


# --- The specific over-grants this audit found ------------------------------

def test_kii_ra_cannot_touch_documentary_evidence(db):
    """Was allowed: IsQAOrAdmin lumped KII_RA, DOCUMENTARY_RA and
    QUAN_QA_RA together, so a KII RA could edit document records."""
    client = client_for(Role.KII_RA)
    assert client.get("/api/v1/documents/").status_code == 403
    assert client.get("/api/v1/qa/queue/").status_code == 403


def test_documentary_ra_cannot_touch_kii_records_or_qa_queue(db):
    client = client_for(Role.DOCUMENTARY_RA)
    assert client.get("/api/v1/kii/").status_code == 403
    assert client.get("/api/v1/qa/queue/").status_code == 403


def test_quan_qa_ra_cannot_touch_kii_or_documents(db):
    client = client_for(Role.QUAN_QA_RA)
    assert client.get("/api/v1/kii/").status_code == 403
    assert client.get("/api/v1/documents/").status_code == 403


def test_kii_and_documentary_ras_can_open_their_own_dashboard(db):
    """docs/18 grants both "KII/document dashboard only" -- IsAnalystOrAdmin
    excluded them, so neither could open the one dashboard its row names."""
    for role_name in (Role.KII_RA, Role.DOCUMENTARY_RA):
        resp = client_for(role_name).get("/api/v1/dashboards/kii-documents/")
        assert resp.status_code == 200, f"{role_name} refused its own dashboard"


def test_quan_qa_ra_can_open_the_qa_dashboard(db):
    assert client_for(Role.QUAN_QA_RA).get("/api/v1/dashboards/qa/").status_code == 200
