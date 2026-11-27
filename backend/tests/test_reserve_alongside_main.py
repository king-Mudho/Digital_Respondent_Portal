"""A Reserve contacted alongside its Main, which stays open (PI decision, 27 Nov 2026, four days before data lock).

Not a replacement: the Main case is untouched and can still complete; the Reserve gets its own recorded reason, the PI
as authoriser, an audit entry and a flag naming the Main. Under test that every rule refuses what it should -- a
non-PI authoriser, no reason, an already-active or unpaired Reserve, a Main that has already finished, a held
duplicate -- and that automatic replacement then leaves the pair alone.
"""

import pytest

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.sampling.models import ActivationReason, ReserveStatus
from apps.sampling.services import ALONGSIDE_KEY, activate_reserve_alongside_main, is_invitable


def _user(role, name):
    r, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=name, password="x", role=r)


@pytest.fixture
def pi(db):
    return _user(Role.PI_ADMIN, "alongside_pi")


def test_the_reserve_is_activated_and_its_main_is_left_open(pi, main_case, locked_reserve_case):
    main_case.workflow_status = "S05"
    main_case.save(update_fields=["workflow_status"])
    r = activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="PI decision before data lock")
    assert r.status == ReserveStatus.ACTIVATED and r.activation_reason == ActivationReason.PI_ALONGSIDE_MAIN
    assert r.activated_by == pi and r.metadata[ALONGSIDE_KEY]["main"] == main_case.sample_id
    assert is_invitable(r)
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S05" and is_invitable(main_case)
    ev = AuditEvent.objects.get(action="reserve.activated", object_id=str(r.pk))
    assert ev.metadata["alongside"] == main_case.sample_id and ev.metadata["reason"] == "PI_ALONGSIDE_MAIN"


def test_only_the_pi_authorises_it(main_case, locked_reserve_case):
    for role in (Role.FIELD_COORDINATOR, Role.TELEPHONE_RA, Role.SUPERVISOR_READONLY):
        with pytest.raises(ValueError, match="Only the PI"):
            activate_reserve_alongside_main(locked_reserve_case, authorised_by=_user(role, f"u_{role}"), note="x")
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.LOCKED


def test_a_reason_is_required(pi, locked_reserve_case):
    with pytest.raises(ValueError, match="note"):
        activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="  ")


def test_a_finished_main_needs_no_reserve(pi, main_case, locked_reserve_case):
    main_case.workflow_status = "S10"
    main_case.save(update_fields=["workflow_status"])
    with pytest.raises(ValueError, match="no longer open"):
        activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="x")
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.LOCKED


def test_an_unpaired_or_already_active_reserve_is_refused(pi, main_case, locked_reserve_case, organisation, stratum):
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_sample_case

    lone = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.RESERVE, year=2026)
    with pytest.raises(ValueError, match="not the matched Reserve"):
        activate_reserve_alongside_main(lone, authorised_by=pi, note="x")
    activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="x")
    with pytest.raises(ValueError, match="not a locked Reserve"):
        activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="x")


def test_a_held_duplicate_is_never_activated(pi, main_case, locked_reserve_case):
    locked_reserve_case.metadata = {**(locked_reserve_case.metadata or {}), "duplicate_of": "SID-X"}
    locked_reserve_case.save(update_fields=["metadata"])
    with pytest.raises(ValueError, match="duplicate"):
        activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="x")


def test_automatic_replacement_then_leaves_the_pair_alone(pi, main_case, locked_reserve_case):
    """If the Main later fails, there is no locked Reserve left to activate, so the Main keeps its own outcome."""
    from apps.sampling.models import ReplacementPolicy
    from apps.sampling.replacement import replace

    activate_reserve_alongside_main(locked_reserve_case, authorised_by=pi, note="x")
    policy = ReplacementPolicy.objects.create(enabled=True, enabled_by=pi, triggers=["REFUSED"])
    assert replace(main_case, "REFUSED", policy) is None
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.activation_reason == ActivationReason.PI_ALONGSIDE_MAIN
