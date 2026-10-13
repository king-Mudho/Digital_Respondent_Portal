"""
Searching the registers by phone number (api/phone_search.py). Numbers on file are written every way ("+263 77 212
3456", "0772123456", several numbers in one field, ranges like "703961-5"), so the search compares digits only, with
the country code and trunk 0 dropped. What is under test: every way of typing a number finds the record, a number
that is not on file finds nothing, an ordinary search is unchanged, and a Contact RA still sees only their own cases.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent
from apps.kii.services import create_kii_record
from apps.sampling.models import SampleType
from apps.sampling.services import create_organisation, create_sample_case
from api.phone_search import phone_core

pytestmark = pytest.mark.django_db


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(username=username, password="x", role=role)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _found(client, url, term):
    response = client.get(url, {"search": term})
    assert response.status_code == 200
    return response.data["results"]


@pytest.mark.parametrize("term,core", [
    ("0772 123 456", "772123456"), ("+263772123456", "772123456"), ("263 77 212 3456", "772123456"),
    ("(+263) 242-703961", "242703961"), ("772123", "772123"),
    ("0093", ""), ("12345", ""), ("KII-0093", ""), ("Agri Bank", ""), ("S-2026-0001", ""), ("", ""),
])
def test_what_counts_as_a_phone_number(term, core):
    assert phone_core(term) == core


def test_main_400_cases_and_organisations_are_found_by_any_way_of_writing_a_number(organisation, stratum):
    case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    Respondent.objects.create(sample_case=case, full_name="Head office", phone="(+263) 242 70396175 or 0242 703 961")
    Respondent.objects.create(sample_case=case, full_name="Rudo Chikore", whatsapp_number="+263 77 212 3456")
    other_org = create_organisation(name="Other Farms", province=organisation.province, district="Harare",
                                    actor_family=organisation.actor_family, size_class=organisation.size_class)
    other = create_sample_case(organisation=other_org, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    Respondent.objects.create(sample_case=other, full_name="Someone", phone="0712 000 111")
    client, _ = _client("FIELD_COORDINATOR", "phone_fc")

    for term in ("0772123456", "0772 123 456", "+263772123456", "772 123 456", "0242 703 961", "242703961"):
        assert [c["sample_id"] for c in _found(client, "/api/v1/sample-cases/", term)] == [case.sample_id], term
        assert [o["master_id"] for o in _found(client, "/api/v1/organisations/", term)] == [organisation.master_id], term
    assert _found(client, "/api/v1/sample-cases/", "0773 999 888") == []
    # An ordinary search is unchanged, and a case with two matching numbers is listed once.
    assert [c["sample_id"] for c in _found(client, "/api/v1/sample-cases/", "Other Farms")] == [other.sample_id]
    Respondent.objects.create(sample_case=case, full_name="Duplicate", phone="0772123456")
    assert len(_found(client, "/api/v1/sample-cases/", "0772123456")) == 1
    # A number-like term that the ordinary search matches (here, in a name) is still found that way too.
    numbered = create_organisation(name="Plot 4401270 Estates", province=organisation.province, district="Harare",
                                   actor_family=organisation.actor_family, size_class=organisation.size_class)
    assert [o["master_id"] for o in _found(client, "/api/v1/organisations/", "4401270")] == [numbered.master_id]


def test_a_contact_ra_finds_only_their_own_cases_by_phone(organisation, stratum):
    mine = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    theirs = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    for case in (mine, theirs):
        Respondent.objects.create(sample_case=case, full_name="Same switchboard", phone="+263 242 700 100")
    client, ra = _client("CONTACT_RA", "phone_ra")
    mine.assigned_ra = ra
    mine.save(update_fields=["assigned_ra"])
    assert [c["sample_id"] for c in _found(client, "/api/v1/sample-cases/", "0242 700 100")] == [mine.sample_id]


def test_kii_records_are_found_by_phone_or_whatsapp_including_additional_numbers():
    first = create_kii_record(participant_name="Tendai Moyo", participant_role="CEO", stakeholder_category="Bank",
                              status="PROSPECT", phone="+263 242 703961-5; +263 242 703961/9")
    second = create_kii_record(participant_name="Rudo Chikore", participant_role="Head", stakeholder_category="Bank",
                               status="PROSPECT", whatsapp_number="0772 123 456")
    client, _ = _client("KII_RA", "phone_kii_ra")
    assert [r["kii_id"] for r in _found(client, "/api/v1/kii/", "0242 703961")] == [first.kii_id]
    assert [r["kii_id"] for r in _found(client, "/api/v1/kii/", "+263772123456")] == [second.kii_id]
    assert _found(client, "/api/v1/kii/", "0712 000 111") == []
    assert [r["kii_id"] for r in _found(client, "/api/v1/kii/", "Rudo")] == [second.kii_id]
