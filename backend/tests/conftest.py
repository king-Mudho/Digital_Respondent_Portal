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


@pytest.fixture(autouse=True)
def _no_meta_lookup(monkeypatch):
    """Sending WhatsApp asks Twilio whether Meta has approved the template (twilio_client.template_approvals). Tests
    never reach Twilio: no template is known, so none is refused. A test about approval sets its own answer."""
    from apps.messaging import twilio_client as tw

    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [])
    # Meta's limit for the number is read from Twilio too: in tests there is none, so the study's own ceiling applies.
    monkeypatch.setattr(tw, "meta_messaging_limit", lambda **kw: None)


@pytest.fixture(autouse=True)
def _empty_cache():
    """Cached values (KoboToolbox form content, report figures) must not leak
    between tests: test_data_export only passed when it ran before
    test_submission_copies, which had cached different form content."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


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
