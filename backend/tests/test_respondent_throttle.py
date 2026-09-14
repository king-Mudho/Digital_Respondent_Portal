"""
The public respondent journey has its own per-IP throttle scope.

Found 2026-09-14: the respondent endpoints shared the generic `anon` scope
at 30/minute. One respondent's journey costs roughly 8-10 calls, and
Zimbabwe's mobile networks put many subscribers behind shared carrier-grade
NAT addresses, so three or four genuine respondents on one carrier IP in the
same minute were told to wait -- mid-consent. The E2E suite reproduced it.
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from api.throttling import RespondentRateThrottle


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


RESPONDENT_VIEWS = [
    ("apps.invitations.views", "InvitationValidateView"),
    ("apps.contacts.views", "EligibilityView"),
    ("apps.consent.views", "ConsentSubmitView"),
    ("apps.kobo.views", "KoboRedirectURLView"),
    ("apps.proit.views", "RespondentPreProfileView"),
    ("apps.proit.views", "RespondentVerifyView"),
    ("apps.contacts.views", "AppointmentListCreateView"),
]


@pytest.mark.parametrize("module,name", RESPONDENT_VIEWS)
def test_every_respondent_endpoint_uses_the_respondent_scope(module, name):
    import importlib

    view = getattr(importlib.import_module(module), name)
    scopes = {getattr(t, "scope", None) for t in view.throttle_classes}

    assert "respondent" in scopes, f"{name} is not on the respondent scope"
    assert "anon" not in scopes, f"{name} still shares the generic anon bucket"
    assert "invitation_token" in scopes, f"{name} lost its per-token limit"


def test_respondent_rate_is_higher_than_the_generic_anon_rate(settings):
    from rest_framework.throttling import AnonRateThrottle

    respondent = RespondentRateThrottle().num_requests
    anon = AnonRateThrottle().num_requests

    assert respondent > anon


@pytest.mark.django_db
def test_several_respondents_behind_one_address_are_not_turned_away():
    """Four full journeys' worth of validate calls from one IP in one minute
    -- what a WhatsApp invitation wave on a carrier-NAT network looks like --
    must all succeed. At the old 30/minute the fourth respondent failed."""
    # A distinct token per call: these are different respondents sharing one
    # address. Reusing one token string would trip the per-token limit (20)
    # instead and say nothing about the per-IP scope.
    client = APIClient()
    statuses = [
        client.get(f"/api/v1/invitations/validate/?t=respondent-{i}").status_code
        for i in range(40)
    ]

    assert 429 not in statuses


@pytest.mark.django_db
def test_the_respondent_scope_still_throttles_eventually():
    """Raising the limit must not remove it."""
    client = APIClient()
    rate = RespondentRateThrottle().num_requests

    # Distinct tokens again, so the 429 can only come from the per-IP
    # respondent scope -- with one reused token the per-token limit would
    # produce it and this test would pass without proving anything.
    statuses = [
        client.get(f"/api/v1/invitations/validate/?t=probe-{i}").status_code
        for i in range(rate + 5)
    ]

    assert 429 not in statuses[:rate], "throttled before the respondent limit was reached"
    assert 429 in statuses[rate:], "the respondent scope never throttles"
