"""
Closes a real admin-UI gap: there was no way to register an organisation or
create its sample case from the Research Operations Centre at all -- only
Django admin, requiring three separate screens (Organisations, Stratum
definitions, Sample cases) and manual stratum matching. OrganisationSerializer
already existed but had no view; SampleCase creation required a pre-existing
stratum id.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.sampling.models import Organisation, SampleCase, StratumDefinition
from apps.sampling.services import resolve_stratum_for_organisation


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="org_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


ORG_PAYLOAD = {
    "name": "Test Registration Org",
    "entity_type": "Cooperative",
    "province": "HARARE",
    "district": "Harare",
    "actor_family": "PRODUCER_PRIMARY",
    "value_chain": "Horticulture",
    "size_class": "SME",
}


def test_create_organisation_generates_master_id(admin_client):
    resp = admin_client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json")
    assert resp.status_code == 201
    assert resp.data["master_id"].startswith("MID-HA-")
    assert Organisation.objects.filter(name="Test Registration Org").exists()


def test_organisation_list_requires_authentication():
    client = APIClient()
    assert client.get("/api/v1/organisations/").status_code in (401, 403)


def test_sample_case_creation_auto_resolves_stratum_when_omitted(admin_client):
    org_resp = admin_client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json")
    org_id = org_resp.data["id"]

    resp = admin_client.post(
        "/api/v1/sample-cases/",
        {"organisation": org_id, "sample_type": "MAIN", "year": 2026},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["sample_id"].startswith("SID-2026-")
    case = SampleCase.objects.get(pk=resp.data["id"])
    assert case.stratum.province == "HARARE"
    assert case.stratum.actor_family == "PRODUCER_PRIMARY"


def test_sample_case_creation_reuses_existing_stratum_not_a_duplicate(admin_client):
    org1 = admin_client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json").data
    org2 = admin_client.post(
        "/api/v1/organisations/", {**ORG_PAYLOAD, "name": "Second Org"}, format="json"
    ).data

    admin_client.post("/api/v1/sample-cases/", {"organisation": org1["id"], "sample_type": "MAIN"}, format="json")
    admin_client.post("/api/v1/sample-cases/", {"organisation": org2["id"], "sample_type": "RESERVE"}, format="json")

    assert StratumDefinition.objects.filter(
        province="HARARE", actor_family="PRODUCER_PRIMARY", size_class="SME",
    ).count() == 1


def test_resolve_stratum_for_organisation_is_idempotent(organisation):
    first = resolve_stratum_for_organisation(organisation)
    second = resolve_stratum_for_organisation(organisation)
    assert first.id == second.id


def test_duplicate_stratum_definitions_for_the_same_combination_are_rejected(organisation):
    """Found live on research.agribizframework.com: two StratumDefinition rows
    (different `code`) existed for the same province/actor_family/size_class,
    so resolve_stratum_for_organisation()'s get_or_create() raised
    MultipleObjectsReturned instead of finding one. migrations/
    0003_stratumdefinition_unique_combo.py merged the existing duplicates and
    added a DB constraint -- this confirms a second row for an
    already-resolved combination can no longer be created at all."""
    from django.db import IntegrityError

    resolve_stratum_for_organisation(organisation)
    with pytest.raises(IntegrityError):
        StratumDefinition.objects.create(
            code="a-second-code-for-the-same-combination",
            province=organisation.province,
            actor_family=organisation.actor_family,
            size_class=organisation.size_class,
            target_count=10,
        )


def test_contact_ra_can_list_but_not_create_organisations(db):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="contact_ra_org_test", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.get("/api/v1/organisations/").status_code == 200
    assert client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json").status_code == 403


# --- Correcting an already-saved organisation (2026-10-01) -------------------
# There was previously no way to fix a mistyped organisation name at all --
# OrganisationSerializer existed but OrganisationListCreateView only supported
# GET/POST, never a detail/update route.

def test_pi_can_correct_an_organisations_name(admin_client, organisation):
    resp = admin_client.patch(
        f"/api/v1/organisations/{organisation.id}/",
        {"name": "Corrected Name (Pvt) Ltd", "district": "Chitungwiza"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    organisation.refresh_from_db()
    assert organisation.name == "Corrected Name (Pvt) Ltd"
    assert organisation.district == "Chitungwiza"


def test_editing_an_organisation_cannot_change_its_stratifying_fields(admin_client, organisation):
    """province/actor_family/size_class drive resolve_stratum_for_organisation()
    at case-creation time only (apps/sampling/services.py) -- a stratum is never
    re-resolved afterwards. Letting these change here would silently detach an
    organisation from the StratumDefinition its existing SampleCase was paired
    and Reserve-matched against, which AGENTS.md ground rule 4 treats as a
    database-enforced invariant, not a UI convenience. The province code is also
    baked into the immutable master_id."""
    original_master_id = organisation.master_id
    resp = admin_client.patch(
        f"/api/v1/organisations/{organisation.id}/",
        {"province": "BULAWAYO", "actor_family": "FINANCE_INSURANCE", "size_class": "LARGE_CORPORATE"},
        format="json",
    )
    assert resp.status_code == 200  # PATCH still succeeds -- it just ignores these fields
    organisation.refresh_from_db()
    assert organisation.province == "HARARE"
    assert organisation.actor_family == "PRODUCER_PRIMARY"
    assert organisation.size_class == "SME"
    assert organisation.master_id == original_master_id


def test_organisation_detail_requires_field_coordinator_or_admin(organisation):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="contact_ra_edit_org", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.patch(f"/api/v1/organisations/{organisation.id}/", {"name": "Should not land"}, format="json")
    assert resp.status_code == 403
    organisation.refresh_from_db()
    assert organisation.name != "Should not land"
