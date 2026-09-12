"""
Sep 2026 hardening pass: CONTACT_RA was not included in ANY permission
class -- every internal endpoint returned 403 regardless of what the
account tried to do. SUPERVISOR_READONLY was under-granted (missing read
access to sample cases/contacts docs/18 calls "Read-only, all") and
over-granted (included in the export permission, which docs/18 explicitly
denies it). This file exercises both roles end-to-end through the actual
DRF views, not just the permission class in isolation.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


def _client_for(role_name, username, db):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(username=username, password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    client.user = user  # for tests that need to assign a case to this exact user
    return client


@pytest.fixture
def contact_ra_client(db):
    return _client_for("CONTACT_RA", "contact_ra_test", db)


@pytest.fixture
def supervisor_client(db):
    return _client_for("SUPERVISOR_READONLY", "supervisor_test", db)


@pytest.fixture
def field_coordinator_client(db):
    return _client_for("FIELD_COORDINATOR", "field_coordinator_test", db)


# --- Contact RA --------------------------------------------------------------

def test_contact_ra_can_view_assigned_sample_case(contact_ra_client, main_case):
    main_case.assigned_ra = contact_ra_client.user
    main_case.save(update_fields=["assigned_ra"])
    assert contact_ra_client.get("/api/v1/sample-cases/").status_code == 200
    assert contact_ra_client.get(f"/api/v1/sample-cases/{main_case.sample_id}/").status_code == 200


def test_contact_ra_cannot_see_a_case_not_assigned_to_them(contact_ra_client, main_case):
    """docs/18: Contact RA gets "assigned cases", not every case. An
    unassigned case is invisible in the list and 404s on direct lookup
    (not 403 -- its existence isn't confirmed or denied either way)."""
    resp = contact_ra_client.get("/api/v1/sample-cases/")
    assert resp.status_code == 200
    assert all(r["sample_id"] != main_case.sample_id for r in resp.data["results"])
    assert contact_ra_client.get(f"/api/v1/sample-cases/{main_case.sample_id}/").status_code == 404


def test_contact_ra_cannot_log_contact_events_for_an_unassigned_case(contact_ra_client, main_case):
    resp = contact_ra_client.post(
        f"/api/v1/contacts/{main_case.sample_id}/events/",
        {"channel": "PHONE", "occurred_at": "2026-09-12T10:00:00Z", "outcome": "REACHED"},
        format="json",
    )
    assert resp.status_code == 403


def test_contact_ra_cannot_write_sample_case(contact_ra_client, main_case):
    """Read-only on sample cases -- reserve activation, workflow transition
    and PATCH remain Field Coordinator/Admin authority."""
    resp = contact_ra_client.patch(f"/api/v1/sample-cases/{main_case.sample_id}/", {"stratum": 1}, format="json")
    assert resp.status_code == 403
    resp = contact_ra_client.post(f"/api/v1/sample-cases/{main_case.sample_id}/transition/", {"workflow_status": "S01"}, format="json")
    assert resp.status_code == 403
    resp = contact_ra_client.post(f"/api/v1/sample-cases/{main_case.sample_id}/activate-reserve/", {"activation_reason": "REFUSAL"}, format="json")
    assert resp.status_code == 403


def test_contact_ra_can_log_contact_events_and_manage_appointments_for_assigned_case(contact_ra_client, main_case):
    main_case.assigned_ra = contact_ra_client.user
    main_case.save(update_fields=["assigned_ra"])
    resp = contact_ra_client.post(
        f"/api/v1/contacts/{main_case.sample_id}/events/",
        {"channel": "PHONE", "occurred_at": "2026-09-12T10:00:00Z", "outcome": "REACHED"},
        format="json",
    )
    assert resp.status_code == 201
    assert contact_ra_client.get("/api/v1/appointments/").status_code == 200


def test_contact_ra_can_issue_and_revoke_invitations_for_assigned_case(contact_ra_client, main_case):
    main_case.assigned_ra = contact_ra_client.user
    main_case.save(update_fields=["assigned_ra"])
    resp = contact_ra_client.post(
        "/api/v1/invitations/", {"sample_id": main_case.sample_id, "channel": "WHATSAPP"}, format="json"
    )
    assert resp.status_code == 201
    token_id = resp.data["token_id"]
    resp = contact_ra_client.post(f"/api/v1/invitations/{token_id}/revoke/", {"reason": "test"}, format="json")
    assert resp.status_code == 200


def test_contact_ra_cannot_issue_invitation_for_an_unassigned_case(contact_ra_client, main_case):
    resp = contact_ra_client.post(
        "/api/v1/invitations/", {"sample_id": main_case.sample_id, "channel": "WHATSAPP"}, format="json"
    )
    assert resp.status_code == 403


def test_contact_ra_cannot_log_cost_events_or_trigger_kobo_sync(contact_ra_client):
    """Confirms the fix stayed narrow -- Contact RA gets contact-focused
    access, not the full Field Coordinator grant."""
    resp = contact_ra_client.post("/api/v1/costs/", {"date": "2026-09-12", "category": "TRANSPORT", "amount": "10.00"}, format="json")
    assert resp.status_code == 403
    resp = contact_ra_client.post("/api/v1/kobo/reconcile/")
    assert resp.status_code == 403


def test_contact_ra_has_no_dashboard_or_kii_or_document_access(contact_ra_client, main_case):
    """docs/18: Contact RA's dashboard/KII/document columns are all "No"."""
    assert contact_ra_client.get("/api/v1/dashboards/contact/").status_code == 403
    assert contact_ra_client.get("/api/v1/kii/").status_code == 403
    assert contact_ra_client.get("/api/v1/documents/").status_code == 403
    assert contact_ra_client.get("/api/v1/qa/queue/").status_code == 403


# --- Supervisor (read-only) ---------------------------------------------------

def test_supervisor_can_read_sample_cases_contacts_kii_documents_qa(supervisor_client, main_case):
    assert supervisor_client.get("/api/v1/sample-cases/").status_code == 200
    assert supervisor_client.get(f"/api/v1/sample-cases/{main_case.sample_id}/").status_code == 200
    assert supervisor_client.get(f"/api/v1/contacts/{main_case.sample_id}/events/").status_code == 200
    assert supervisor_client.get("/api/v1/appointments/").status_code == 200
    assert supervisor_client.get("/api/v1/kii/").status_code == 200
    assert supervisor_client.get("/api/v1/documents/").status_code == 200
    assert supervisor_client.get("/api/v1/qa/queue/").status_code == 200
    assert supervisor_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}").status_code == 200


def test_supervisor_can_read_every_dashboard(supervisor_client, main_case):
    for url in (
        "/api/v1/dashboards/executive/",
        "/api/v1/dashboards/sampling/",
        "/api/v1/dashboards/contact/",
        "/api/v1/dashboards/qa/",
        "/api/v1/dashboards/kii-documents/",
        "/api/v1/dashboards/cost/",
    ):
        assert supervisor_client.get(url).status_code == 200, url


def test_supervisor_cannot_write_anywhere(supervisor_client, main_case):
    """The "read-only" half of "Read-only, all" -- every write path stays
    blocked even though the read path now works."""
    assert supervisor_client.patch(f"/api/v1/sample-cases/{main_case.sample_id}/", {"stratum": 1}, format="json").status_code == 403
    assert supervisor_client.post(
        f"/api/v1/contacts/{main_case.sample_id}/events/",
        {"channel": "PHONE", "occurred_at": "2026-09-12T10:00:00Z", "outcome": "REACHED"},
        format="json",
    ).status_code == 403
    assert supervisor_client.post("/api/v1/invitations/", {"sample_id": main_case.sample_id}, format="json").status_code == 403
    assert supervisor_client.post("/api/v1/costs/", {"date": "2026-09-12", "category": "TRANSPORT", "amount": "10"}, format="json").status_code == 403
    assert supervisor_client.post("/api/v1/kobo/reconcile/").status_code == 403


def test_supervisor_cannot_export_deidentified_data(supervisor_client):
    """docs/18: export column is explicitly "No" for Supervisor, even
    though it has full dashboard access -- these must not be the same
    permission grant."""
    assert supervisor_client.get("/api/v1/export/analysis/").status_code == 403


def test_supervisor_cannot_access_operational_export_or_audit_log(supervisor_client):
    assert supervisor_client.get("/api/v1/export/operational/").status_code == 403
    assert supervisor_client.get("/api/v1/audit/").status_code == 403


# --- Confirms Field Coordinator's existing access is unaffected --------------

def test_field_coordinator_retains_full_prior_access(field_coordinator_client, main_case, locked_reserve_case):
    assert field_coordinator_client.get("/api/v1/sample-cases/").status_code == 200
    assert field_coordinator_client.post(
        f"/api/v1/sample-cases/{main_case.sample_id}/transition/", {"workflow_status": "S01"}, format="json"
    ).status_code == 200
    assert field_coordinator_client.post("/api/v1/costs/", {"date": "2026-09-12", "category": "TRANSPORT", "amount": "10.00"}, format="json").status_code == 201
    assert field_coordinator_client.get("/api/v1/dashboards/executive/").status_code == 200
    # Still excluded, per docs/18's export column ("No" for Field Coordinator)
    # -- this pass didn't touch that pre-existing behaviour, only Supervisor's.


def test_field_coordinator_can_still_export_deidentified_data(field_coordinator_client):
    """Not part of this fix's scope -- CanExportDeidentified deliberately
    keeps Field Coordinator's existing access unchanged, only Supervisor's
    over-grant was removed."""
    assert field_coordinator_client.get("/api/v1/export/analysis/").status_code == 200
