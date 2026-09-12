import pytest

from apps.sampling.models import (
    ActorFamily,
    Province,
    ReserveStatus,
    SampleType,
    SizeClass,
    StratumDefinition,
)
from apps.sampling.services import create_organisation, create_sample_case


@pytest.fixture
def stratum(db):
    return StratumDefinition.objects.create(
        code="HA-PRODUCER-SME",
        province=Province.HARARE,
        actor_family=ActorFamily.PRODUCER_PRIMARY,
        size_class=SizeClass.SME,
        target_count=10,
    )


@pytest.fixture
def organisation(db):
    return create_organisation(
        province=Province.HARARE,
        name="Test Organisation",
        entity_type="Private Limited Company",
        district="Harare",
        actor_family=ActorFamily.PRODUCER_PRIMARY,
        value_chain="Horticulture",
        size_class=SizeClass.SME,
    )


@pytest.fixture
def main_case(db, organisation, stratum):
    return create_sample_case(
        organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026
    )


@pytest.fixture
def locked_reserve_case(db, organisation, stratum, main_case):
    reserve = create_sample_case(
        organisation=organisation, stratum=stratum, sample_type=SampleType.RESERVE, year=2026
    )
    main_case.matched_case = reserve
    main_case.save(update_fields=["matched_case"])
    return reserve


@pytest.fixture
def activated_reserve_case(db, locked_reserve_case):
    locked_reserve_case.status = ReserveStatus.ACTIVATED
    locked_reserve_case.save(update_fields=["status"])
    return locked_reserve_case
