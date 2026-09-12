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
    "entity_type": "COOPERATIVE",
    "province": "HARARE",
    "district": "Harare",
    "actor_family": "PRODUCER_FARMER",
    "value_chain": "HORTICULTURE",
    "size_class": "SMALL",
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
    assert case.stratum.actor_family == "PRODUCER_FARMER"


def test_sample_case_creation_reuses_existing_stratum_not_a_duplicate(admin_client):
    org1 = admin_client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json").data
    org2 = admin_client.post(
        "/api/v1/organisations/", {**ORG_PAYLOAD, "name": "Second Org"}, format="json"
    ).data

    admin_client.post("/api/v1/sample-cases/", {"organisation": org1["id"], "sample_type": "MAIN"}, format="json")
    admin_client.post("/api/v1/sample-cases/", {"organisation": org2["id"], "sample_type": "RESERVE"}, format="json")

    assert StratumDefinition.objects.filter(
        province="HARARE", actor_family="PRODUCER_FARMER", value_chain="HORTICULTURE", size_class="SMALL",
    ).count() == 1


def test_resolve_stratum_for_organisation_is_idempotent(organisation):
    first = resolve_stratum_for_organisation(organisation)
    second = resolve_stratum_for_organisation(organisation)
    assert first.id == second.id


def test_contact_ra_can_list_but_not_create_organisations(db):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="contact_ra_org_test", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.get("/api/v1/organisations/").status_code == 200
    assert client.post("/api/v1/organisations/", ORG_PAYLOAD, format="json").status_code == 403
