import pytest

from apps.sampling.models import (
    ActorFamily,
    EntityType,
    Province,
    ReserveStatus,
    SampleType,
    SizeClass,
    StratumDefinition,
    ValueChain,
)
from apps.sampling.services import create_organisation, create_sample_case


@pytest.fixture
def stratum(db):
    return StratumDefinition.objects.create(
        code="HA-PRODUCER-HORTICULTURE-SMALL",
        province=Province.HARARE,
        actor_family=ActorFamily.PRODUCER_FARMER,
        value_chain=ValueChain.HORTICULTURE,
        size_class=SizeClass.SMALL,
        target_count=10,
    )


@pytest.fixture
def organisation(db):
    return create_organisation(
        province=Province.HARARE,
        name="Test Organisation",
        entity_type=EntityType.PRIVATE_LIMITED_COMPANY,
        district="Harare",
        actor_family=ActorFamily.PRODUCER_FARMER,
        value_chain=ValueChain.HORTICULTURE,
        size_class=SizeClass.SMALL,
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
