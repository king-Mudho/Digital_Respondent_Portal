"""Twilio's delivery reports and incoming messages have their own throttle scope (api/throttling.TwilioWebhookThrottle,
2026-10-13). Until then they shared the respondents' 30/minute per-IP allowance, so one WhatsApp batch's delivery
reports (up to four per message, from a few Twilio addresses) would mostly have been refused -- and Twilio does not
resend a refused status callback."""

from urllib.parse import urlencode

from rest_framework.test import APIClient

from apps.messaging import twilio_client as tw
from tests.test_outreach import STATUS, _sign


def test_a_burst_of_delivery_reports_from_one_address_is_never_refused(settings, db):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    client = APIClient()
    codes = set()
    for n in range(80):  # well past the respondents' 30/minute
        params = {"MessageSid": f"SMburst{n}", "MessageStatus": "delivered"}
        codes.add(client.post(STATUS, urlencode(params), content_type="application/x-www-form-urlencoded",
                              HTTP_X_TWILIO_SIGNATURE=_sign(tw.status_callback_url(), params), REMOTE_ADDR="54.172.60.1").status_code)
    assert 429 not in codes and codes <= {200, 204}


def test_an_unsigned_post_is_still_refused(settings, db):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    resp = APIClient().post(STATUS, urlencode({"MessageSid": "SMx", "MessageStatus": "delivered"}),
                            content_type="application/x-www-form-urlencoded", HTTP_X_TWILIO_SIGNATURE="forged")
    assert resp.status_code == 403
