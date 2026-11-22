"""The Twilio balance on the Cost screen (22 Nov 2026): what is left, what was spent this month and in the last 7 days,
the daily rate and how many days remain, with a warning below the configured levels; read-only and cached; a Twilio
failure is reported, never raised; only the Cost screen's roles may read it."""

from datetime import date
from unittest.mock import Mock

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.messaging import twilio_client as tw

pytestmark = pytest.mark.django_db


def _get(balance="14.7766", week=4.83, month=5.89, wa_week=2.88, wa_month=3.46):
    def get(url, params=None, auth=None, timeout=None):
        if url.endswith("/Balance.json"):
            return Mock(ok=True, status_code=200, json=Mock(return_value={"balance": balance, "currency": "USD"}))
        start, category = params["StartDate"], params["Category"]
        weekly = start == "2026-11-16"
        price = {"totalprice": week if weekly else month, "channels-whatsapp": wa_week if weekly else wa_month}[category]
        return Mock(ok=True, json=Mock(return_value={"usage_records": [{"price": str(price), "count": "293" if weekly else "369"}]}))
    return get


@pytest.fixture
def twilio(settings):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret"
    settings.TWILIO_BALANCE_WARN_USD, settings.TWILIO_BALANCE_WARN_DAYS = 5.0, 7


def test_the_balance_spending_and_days_left(twilio):
    out = tw.account_balance(get=_get(), today=date(2026, 11, 22))
    assert out["balance"] == 14.78 and out["spent_this_month"] == 5.89 and out["spent_last_7_days"] == 4.83
    assert out["per_day"] == 0.69 and out["days_left"] == 21 and out["runs_out_on"] == "2026-12-13"
    assert out["whatsapp_messages_this_month"] == 369 and out["low"] is False


def test_it_warns_below_the_configured_days(twilio):
    out = tw.account_balance(get=_get(balance="3.00"), today=date(2026, 11, 22))
    assert out["days_left"] == 4 and out["low"] is True


def test_a_twilio_failure_is_reported_not_raised(twilio):
    def broken(*a, **k):
        raise tw.requests.ConnectionError()
    assert "could not be reached" in tw.account_balance(get=broken, today=date(2026, 11, 22))["error"]


def test_only_the_cost_screens_roles_read_it(twilio, monkeypatch):
    monkeypatch.setattr(tw, "account_balance", lambda: {"configured": True, "balance": 1.0})
    for role, allowed in ((Role.PI_ADMIN, True), (Role.ANALYST, True), (Role.TELEPHONE_RA, False), (Role.CONTACT_RA, False)):
        r, _ = Role.objects.get_or_create(name=role)
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username=f"bal_{role.lower()}", password="x", role=r))
        assert (client.get("/api/v1/dashboards/twilio-balance/").status_code == 200) is allowed
