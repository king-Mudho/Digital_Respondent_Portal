"""
Main <-> Reserve pairing (SampleCase.matched_case).

The 400 pairs were wired directly by import_quan_register; for an
organisation added afterwards there was no path at all short of Django
admin, and `matched_case` was a bare FK with no validation. The API would
accept a Main paired to another Main, a case paired to itself, or the same
Reserve handed to two different Main cases -- the last of which silently
breaks the reserve lock, since activating that one Reserve would appear to
cover both Main cases.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.sampling.models import (
    ActorFamily,
    Province,
    ReserveStatus,
    SampleType,
    SizeClass,
    StratumDefinition,
)
from apps.sampling.services import (
    InvalidMatchedCase,
    available_reserves_for,
    create_organisation,
    create_sample_case,
    set_matched_case,
)


@pytest.fixture
def coordinator(db):
    role, _ = Role.objects.get_or_create(name=Role.FIELD_COORDINATOR)
    return User.objects.create_user(username="match_fc", password="testpass123", role=role)


@pytest.fixture
def coordinator_client(coordinator):
    client = APIClient()
    client.force_authenticate(user=coordinator)
    return client


@pytest.fixture
def contact_ra_client(db):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="match_ra", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _case(stratum, sample_type, name):
    org = create_organisation(
        province=Province.HARARE, name=name, entity_type="Cooperative", district="Harare",
        actor_family=ActorFamily.PRODUCER_PRIMARY, value_chain="Horticulture",
        size_class=SizeClass.SME,
    )
    return create_sample_case(organisation=org, stratum=stratum, sample_type=sample_type, year=2026)


@pytest.fixture
def other_stratum(db):
    return StratumDefinition.objects.create(
        code="BY-PROCESSING-MICRO", province=Province.BULAWAYO,
        actor_family=ActorFamily.PROCESSING_MANUFACTURING, size_class=SizeClass.MICRO,
        target_count=5,
    )


# --- the service ---------------------------------------------------------

def test_pairing_records_the_match_and_an_audit_entry(main_case, stratum, coordinator):
    reserve = _case(stratum, SampleType.RESERVE, "Reserve Co")

    set_matched_case(main_case, reserve, changed_by=coordinator)

    main_case.refresh_from_db()
    assert main_case.matched_case_id == reserve.id
    event = AuditEvent.objects.filter(action="sample_case.matched").latest("created_at")
    assert event.metadata["matched_sample_id"] == reserve.sample_id
    assert event.metadata["same_stratum"] is True


def test_a_reserve_cannot_be_claimed_by_two_main_cases(main_case, stratum, coordinator):
    """The one that actually breaks the reserve lock: activating a shared
    Reserve would look like it covered both Main cases."""
    reserve = _case(stratum, SampleType.RESERVE, "Contested Reserve")
    other_main = _case(stratum, SampleType.MAIN, "Other Main Co")
    set_matched_case(main_case, reserve, changed_by=coordinator)

    with pytest.raises(InvalidMatchedCase, match=main_case.sample_id):
        set_matched_case(other_main, reserve, changed_by=coordinator)

    other_main.refresh_from_db()
    assert other_main.matched_case_id is None


def test_a_main_case_cannot_be_matched_to_another_main_case(main_case, stratum, coordinator):
    other_main = _case(stratum, SampleType.MAIN, "Second Main Co")

    with pytest.raises(InvalidMatchedCase, match="must be a RESERVE"):
        set_matched_case(main_case, other_main, changed_by=coordinator)


def test_a_case_cannot_be_matched_to_itself(main_case, coordinator):
    with pytest.raises(InvalidMatchedCase):
        set_matched_case(main_case, main_case, changed_by=coordinator)


def test_only_a_main_case_can_be_given_a_match(stratum, coordinator):
    reserve_a = _case(stratum, SampleType.RESERVE, "Reserve A")
    reserve_b = _case(stratum, SampleType.RESERVE, "Reserve B")

    with pytest.raises(InvalidMatchedCase, match="Only a MAIN case"):
        set_matched_case(reserve_a, reserve_b, changed_by=coordinator)


def test_an_activated_reserve_cannot_be_assigned_as_a_new_match(main_case, stratum, coordinator):
    reserve = _case(stratum, SampleType.RESERVE, "Already Activated")
    reserve.status = ReserveStatus.ACTIVATED
    reserve.save(update_fields=["status"])

    with pytest.raises(InvalidMatchedCase, match="already been activated"):
        set_matched_case(main_case, reserve, changed_by=coordinator)


def test_re_pairing_the_same_reserve_to_the_same_main_is_allowed(main_case, stratum, coordinator):
    """Saving the form again without changing the selection must not trip
    the already-claimed check against the case's own existing match."""
    reserve = _case(stratum, SampleType.RESERVE, "Stable Reserve")
    set_matched_case(main_case, reserve, changed_by=coordinator)

    set_matched_case(main_case, reserve, changed_by=coordinator)

    main_case.refresh_from_db()
    assert main_case.matched_case_id == reserve.id


def test_clearing_the_match_is_audited(main_case, stratum, coordinator):
    reserve = _case(stratum, SampleType.RESERVE, "To Be Cleared")
    set_matched_case(main_case, reserve, changed_by=coordinator)

    set_matched_case(main_case, None, changed_by=coordinator)

    main_case.refresh_from_db()
    assert main_case.matched_case_id is None
    event = AuditEvent.objects.filter(action="sample_case.match_cleared").latest("created_at")
    assert event.metadata["previous_matched_sample_id"] == reserve.sample_id


def test_cross_stratum_pairing_is_allowed_but_flagged(main_case, other_stratum, coordinator):
    """There may be no same-stratum Reserve left, so this is a decision for
    the PI rather than something to refuse -- but it weakens the stratified
    design, so it is never silent."""
    reserve = _case(other_stratum, SampleType.RESERVE, "Different Stratum Reserve")

    set_matched_case(main_case, reserve, changed_by=coordinator)

    event = AuditEvent.objects.filter(action="sample_case.matched").latest("created_at")
    assert event.metadata["same_stratum"] is False


# --- candidate list ------------------------------------------------------

def test_available_reserves_excludes_claimed_and_activated(main_case, stratum, coordinator):
    free = _case(stratum, SampleType.RESERVE, "Free Reserve")
    claimed = _case(stratum, SampleType.RESERVE, "Claimed Reserve")
    activated = _case(stratum, SampleType.RESERVE, "Activated Reserve")
    activated.status = ReserveStatus.ACTIVATED
    activated.save(update_fields=["status"])
    set_matched_case(_case(stratum, SampleType.MAIN, "Claimer"), claimed, changed_by=coordinator)

    ids = {c.sample_id for c in available_reserves_for(main_case)}

    assert free.sample_id in ids
    assert claimed.sample_id not in ids
    assert activated.sample_id not in ids


def test_available_reserves_includes_this_cases_own_current_match(main_case, stratum, coordinator):
    """Otherwise the picker would show the current selection as missing."""
    mine = _case(stratum, SampleType.RESERVE, "My Current Reserve")
    set_matched_case(main_case, mine, changed_by=coordinator)

    assert mine.sample_id in {c.sample_id for c in available_reserves_for(main_case)}


def test_available_reserves_puts_same_stratum_first(main_case, stratum, other_stratum):
    _case(other_stratum, SampleType.RESERVE, "AAA Other Stratum")
    same = _case(stratum, SampleType.RESERVE, "ZZZ Same Stratum")

    first = list(available_reserves_for(main_case))[0]

    assert first.sample_id == same.sample_id


# --- the API -------------------------------------------------------------

def test_coordinator_can_pair_via_the_api(coordinator_client, main_case, stratum):
    reserve = _case(stratum, SampleType.RESERVE, "API Reserve")

    resp = coordinator_client.patch(
        f"/api/v1/sample-cases/{main_case.sample_id}/", {"matched_case": reserve.id}, format="json"
    )

    assert resp.status_code == 200
    assert resp.json()["matched_case_sample_id"] == reserve.sample_id
    main_case.refresh_from_db()
    assert main_case.matched_case_id == reserve.id


def test_api_rejects_an_invalid_pairing_with_a_readable_message(coordinator_client, main_case, stratum, coordinator):
    reserve = _case(stratum, SampleType.RESERVE, "Taken Reserve")
    set_matched_case(_case(stratum, SampleType.MAIN, "First Claimer"), reserve, changed_by=coordinator)

    resp = coordinator_client.patch(
        f"/api/v1/sample-cases/{main_case.sample_id}/", {"matched_case": reserve.id}, format="json"
    )

    assert resp.status_code == 400
    assert "already the match for" in str(resp.json())
    main_case.refresh_from_db()
    assert main_case.matched_case_id is None


def test_available_reserves_endpoint(coordinator_client, main_case, stratum):
    reserve = _case(stratum, SampleType.RESERVE, "Listed Reserve")

    resp = coordinator_client.get(f"/api/v1/sample-cases/{main_case.sample_id}/available-reserves/")

    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert reserve.sample_id in {r["sample_id"] for r in rows}
    assert all("same_stratum" in r for r in rows)


def test_contact_ra_cannot_pair_or_list_candidates(contact_ra_client, main_case, stratum):
    reserve = _case(stratum, SampleType.RESERVE, "Off Limits Reserve")

    patch = contact_ra_client.patch(
        f"/api/v1/sample-cases/{main_case.sample_id}/", {"matched_case": reserve.id}, format="json"
    )
    listing = contact_ra_client.get(f"/api/v1/sample-cases/{main_case.sample_id}/available-reserves/")

    assert patch.status_code == 403
    assert listing.status_code == 403
    main_case.refresh_from_db()
    assert main_case.matched_case_id is None
