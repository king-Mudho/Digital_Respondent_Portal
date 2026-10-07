"""SMS and WhatsApp through Twilio (apps/messaging/twilio_client.py, outbound.py, 2026-10-07). Twilio is replaced by a
fake requests.post that records what would have been sent. Under test:

- the request Twilio receives for an SMS and a WhatsApp template, and Twilio's errors in plain words;
- the delivery webhook: a missing or forged signature is refused, a signed report updates the message, never
  backwards, and an undelivered reminder goes back to a person;
- invitations one case at a time (Main-400 and KII): only with the invitation's own link, only to a mobile, an RA only
  for their own case, nothing when the channel is not set up;
- batches: one invitation sent on every chosen channel, undone when nothing gets through, never a locked Reserve;
- automatic reminders: WhatsApp when its template is set up, otherwise SMS; never to a landline, an expired link or
  a case with a booked call; a refused or undelivered reminder is left for a person and never re-sent;
- the daily caps.
"""

import base64
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations import batch as b
from apps.invitations.models import InvitationToken
from apps.invitations.services import issue_invitation
from apps.messaging import outbound
from apps.messaging import twilio_client as tw
from apps.messaging.models import MessageLog, MessageStatus, ProviderMessage, ProviderStatus
from apps.messaging.services import dispatch_due_reminders, due_follow_ups, exhaust_nonresponse_cases
from apps.sampling.services import transition_workflow_status

WEBHOOK = "/api/v1/twilio/status/"


@pytest.fixture
def twilio(settings, monkeypatch):
    """Twilio set up for SMS (and WhatsApp when a test adds the WhatsApp settings), recording every request."""
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM = "CUT-ABFFST"
    settings.TWILIO_WHATSAPP_FROM = ""
    settings.TWILIO_WA_CONTENT_INVITATION = settings.TWILIO_WA_CONTENT_KII_INVITATION = ""
    settings.TWILIO_WA_CONTENT_REMINDER_DAY2 = settings.TWILIO_WA_CONTENT_REMINDER_DAY7 = ""
    settings.TWILIO_SMS_OPT_OUT_LINE = ""
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    settings.INVITATION_EMAIL_PAUSE_SECONDS = 0
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    sent, answers = [], []

    def post(url, data=None, auth=None, timeout=None):
        sent.append({"url": url, "data": data, "auth": auth})
        status, body = answers.pop(0) if answers else (201, {"sid": f"SM{len(sent):04d}", "status": "queued", "num_segments": "2"})
        return Mock(status_code=status, json=Mock(return_value=body))

    monkeypatch.setattr(tw.requests, "post", post)
    post.sent, post.answers = sent, answers
    return post


def _whatsapp(settings):
    settings.TWILIO_WHATSAPP_FROM = "+15550001111"
    settings.TWILIO_WA_CONTENT_INVITATION, settings.TWILIO_WA_CONTENT_KII_INVITATION = "HXinvite", "HXkii"
    settings.TWILIO_WA_CONTENT_REMINDER_DAY2, settings.TWILIO_WA_CONTENT_REMINDER_DAY7 = "HXday2", "HXday7"


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _verified(case, *, phone="0771234567", email=""):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    return Respondent.objects.create(sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
                                     is_eligible=True, phone=phone, email=email)


def _issue(client, case):
    return client.post("/api/v1/invitations/", {"sample_id": case.sample_id, "channel": "SMS"}, format="json").data


def _sign(params: dict, token="secret-token") -> str:
    payload = tw.status_callback_url() + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def _report(params: dict, signature: str | None = None):
    """POST a delivery report the way Twilio does: form-encoded, signed in X-Twilio-Signature."""
    headers = {"HTTP_X_TWILIO_SIGNATURE": signature} if signature is not None else {}
    return APIClient().post(WEBHOOK, urlencode(params), content_type="application/x-www-form-urlencoded", **headers)


@pytest.fixture
def admin_client(db):
    return _client(_user(Role.PI_ADMIN, "tw_pi"))


# --- The requests Twilio receives -------------------------------------------------------------------------------

def test_an_sms_goes_to_the_international_number_from_the_study_sender_with_a_delivery_callback(twilio, settings):
    settings.TWILIO_SMS_OPT_OUT_LINE = "To stop messages, call 0773943709."
    result = tw.send_sms("263771234567", "Hello")
    [request] = twilio.sent
    assert request["url"] == "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages.json"
    assert request["auth"] == ("ACtest", "secret-token")
    assert request["data"] == {"To": "+263771234567", "From": "CUT-ABFFST", "Body": "Hello To stop messages, call 0773943709.",
                               "StatusCallback": f"https://{settings.APP_DOMAIN}/api/v1/twilio/status/"}
    assert result["sid"] == "SM0001"


def test_whatsapp_is_always_an_approved_template_with_its_variables(twilio, settings):
    _whatsapp(settings)
    tw.send_whatsapp("263771234567", "HXinvite", {1: "Sable Chickens", 2: "https://x/i/abc", 3: "20 October 2026", 4: "ABCD2345"})
    data = twilio.sent[0]["data"]
    assert (data["To"], data["From"], data["ContentSid"]) == ("whatsapp:+263771234567", "whatsapp:+15550001111", "HXinvite")
    assert json.loads(data["ContentVariables"]) == {"1": "Sable Chickens", "2": "https://x/i/abc", "3": "20 October 2026", "4": "ABCD2345"}
    assert "Body" not in data  # never free text


@pytest.mark.parametrize("code, words", [(21408, "Geo permissions"), (20003, "configure-twilio.sh"), (21614, "not a mobile")])
def test_twilio_errors_come_back_in_words_a_coordinator_can_act_on(twilio, code, words):
    twilio.answers.append((400, {"code": code, "message": "raw"}))
    with pytest.raises(tw.TwilioError, match=words):
        tw.send_sms("263771234567", "Hello")


def test_a_busy_twilio_is_asked_again(twilio, settings, monkeypatch):
    settings.AI_TRANSIENT_RETRY_DELAYS = [1]
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    twilio.answers.append((503, {"message": "busy"}))
    assert tw.send_sms("263771234567", "Hello")["status"] == "queued" and len(twilio.sent) == 2


@pytest.mark.parametrize("text, segments", [("a" * 160, 1), ("a" * 161, 2), ("a" * 306, 2), ("a" * 307, 3), ("’" * 70, 1), ("’" * 71, 2)])
def test_sms_segments_are_counted_as_twilio_charges_them(text, segments):
    assert tw.sms_segments(text) == segments


# --- Delivery reports ----------------------------------------------------------------------------------------------

def _message(case, **extra):
    fields = {"channel": "SMS", "purpose": "INVITATION", "provider_sid": "SM9", "to_masked": "+263 ••• 567", **extra}
    return ProviderMessage.objects.create(sample_case=case, **fields)


def test_a_report_without_a_valid_signature_is_refused(twilio, main_case):
    message = _message(main_case)
    params = {"MessageSid": "SM9", "MessageStatus": "delivered"}
    assert _report(params).status_code == 403
    assert _report(params, _sign(params, token="wrong")).status_code == 403
    assert _report({**params, "MessageStatus": "failed"}, _sign(params)).status_code == 403  # altered after signing
    message.refresh_from_db()
    assert message.status == ProviderStatus.QUEUED


def test_a_signed_report_updates_the_message_and_never_moves_it_backwards(twilio, main_case):
    message = _message(main_case)
    for status in ("delivered", "sent"):  # Twilio's reports can arrive out of order
        params = {"MessageSid": "SM9", "MessageStatus": status}
        assert _report(params, _sign(params)).status_code == 204
    message.refresh_from_db()
    assert message.status == ProviderStatus.DELIVERED


def test_an_undelivered_reminder_goes_back_to_a_person_and_is_audited(twilio, main_case):
    from apps.messaging.models import MessageTemplate

    log = MessageLog.objects.create(sample_case=main_case, template=MessageTemplate.objects.get(name="drp_reminder_day2"),
                                    channel="SMS", status=MessageStatus.SENT)
    _message(main_case, message_log=log, purpose="REMINDER")
    params = {"MessageSid": "SM9", "MessageStatus": "undelivered", "ErrorCode": "30003"}
    _report(params, _sign(params))
    log.refresh_from_db()
    assert log.status == MessageStatus.FAILED
    event = AuditEvent.objects.get(action="twilio.message_failed")
    assert event.metadata["error_code"] == "30003" and "771234567" not in str(event.metadata)


# --- Invitations one case at a time --------------------------------------------------------------------------------

def test_an_invitation_is_sent_by_sms_with_its_own_link_to_the_mobile(twilio, admin_client, main_case):
    _verified(main_case, phone="0242 700000; 0773 248 965")  # a landline first: the mobile is chosen
    data = _issue(admin_client, main_case)
    assert data["sms_configured"] is True and data["whatsapp_configured"] is False
    url = f"/api/v1/invitations/{data['token_id']}/send-sms/"
    forged = admin_client.post(url, {"link": data["link"][:-3] + "xyz", "manual_code": data["raw_manual_code"]}, format="json")
    assert forged.status_code == 400 and twilio.sent == []

    resp = admin_client.post(url, {"link": data["link"], "manual_code": data["raw_manual_code"]}, format="json")
    assert resp.status_code == 200 and resp.data["sent_to"] == "+263 ••• 965"
    [request] = twilio.sent
    assert request["data"]["To"] == "+263773248965" and data["link"] in request["data"]["Body"]
    message = ProviderMessage.objects.get()
    assert (message.purpose, message.invitation_token_id, message.segments) == ("INVITATION", data["token_id"], 2)
    event = AuditEvent.objects.get(action="invitation.sms_sent")
    assert event.metadata["recipient"] == "+263 ••• 965" and "773248965" not in str(event.metadata)


def test_a_whatsapp_invitation_fills_the_template_with_the_organisation_link_expiry_and_code(twilio, settings, admin_client, main_case):
    _whatsapp(settings)
    _verified(main_case)
    data = _issue(admin_client, main_case)
    admin_client.post(f"/api/v1/invitations/{data['token_id']}/send-whatsapp/",
                      {"link": data["link"], "manual_code": data["raw_manual_code"]}, format="json")
    variables = json.loads(twilio.sent[0]["data"]["ContentVariables"])
    assert variables["1"] == main_case.organisation.name and variables["2"] == data["link"]
    assert variables["4"] == data["raw_manual_code"]


def test_nothing_is_sent_to_a_landline_or_when_the_channel_is_not_set_up(twilio, settings, admin_client, main_case):
    _verified(main_case, phone="+263 9 75315")
    data = _issue(admin_client, main_case)
    body = {"link": data["link"], "manual_code": data["raw_manual_code"]}
    assert admin_client.post(f"/api/v1/invitations/{data['token_id']}/send-sms/", body, format="json").data["error"]["code"] == "no_mobile"
    resp = admin_client.post(f"/api/v1/invitations/{data['token_id']}/send-whatsapp/", body, format="json")
    assert resp.status_code == 503 and resp.data["error"]["code"] == "whatsapp_not_configured"
    settings.TWILIO_SMS_FROM = ""
    assert admin_client.post(f"/api/v1/invitations/{data['token_id']}/send-sms/", body, format="json").status_code == 503
    assert twilio.sent == []


def test_a_contact_ra_sends_only_for_their_own_cases(twilio, main_case):
    _verified(main_case)
    mine, other = _user(Role.CONTACT_RA, "tw_ra"), _user(Role.CONTACT_RA, "tw_other")
    main_case.assigned_ra = mine
    main_case.save(update_fields=["assigned_ra"])
    data = _issue(_client(mine), main_case)
    body = {"link": data["link"], "manual_code": data["raw_manual_code"]}
    url = f"/api/v1/invitations/{data['token_id']}/send-sms/"
    assert _client(other).post(url, body, format="json").status_code == 403
    assert _client(_user(Role.SUPERVISOR_READONLY, "tw_sup")).post(url, body, format="json").status_code == 403
    assert _client(mine).post(url, body, format="json").status_code == 200
    assert len(twilio.sent) == 1


def test_a_kii_invitation_is_sent_by_sms(twilio, admin_client):
    from apps.kii.services import create_kii_record

    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Head of Agribusiness",
                               stakeholder_category="Bank, DFI & MFI", phone="0712 345 678",
                               metadata={"organisation_name": "CBZ Bank"})
    data = admin_client.post("/api/v1/kii-invitations/", {"kii_id": record.kii_id, "channel": "SMS"}, format="json").data
    assert data["sms_configured"] is True
    resp = admin_client.post(f"/api/v1/kii-invitations/{data['token_id']}/send-sms/",
                             {"link": data["link"], "manual_code": data["raw_manual_code"]}, format="json")
    assert resp.status_code == 200
    assert twilio.sent[0]["data"]["To"] == "+263712345678" and data["link"] in twilio.sent[0]["data"]["Body"]
    assert ProviderMessage.objects.get().kii_invitation_token_id == data["token_id"]


def test_the_invitation_history_shows_what_twilio_reported(twilio, admin_client, main_case):
    _verified(main_case)
    data = _issue(admin_client, main_case)
    admin_client.post(f"/api/v1/invitations/{data['token_id']}/send-sms/",
                      {"link": data["link"], "manual_code": data["raw_manual_code"]}, format="json")
    [entry] = admin_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}").data["results"]
    assert entry["deliveries"][0]["channel"] == "SMS" and entry["deliveries"][0]["to"] == "+263 ••• 567"


# --- Batches -------------------------------------------------------------------------------------------------------

def test_a_batch_sends_one_invitation_on_every_chosen_channel(twilio, main_case):
    from django.core import mail

    _verified(main_case, email="jane@example.org")
    batch = b.start_batch(1, user=_user(Role.FIELD_COORDINATOR, "tw_fc"), channels=["EMAIL", "SMS"])
    b.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 1 and "email" in batch.results[0]["detail"] and "SMS" in batch.results[0]["detail"]
    [token] = InvitationToken.objects.filter(sample_case=main_case)
    [message] = mail.outbox
    link = message.body.split("/i/", 1)[1].split()[0]
    assert link in twilio.sent[0]["data"]["Body"]  # the same link on both channels


def test_a_batch_undoes_the_invitation_when_nothing_gets_through(twilio, main_case):
    _verified(main_case)
    twilio.answers.append((400, {"code": 21211, "message": "invalid"}))
    batch = b.start_batch(1, user=_user(Role.FIELD_COORDINATOR, "tw_fc2"), channels=["SMS"])
    b.run_batch(batch.pk)
    batch.refresh_from_db()
    main_case.refresh_from_db()
    assert batch.failed == 1 and "not a valid mobile" in batch.results[0]["detail"]
    assert not InvitationToken.objects.filter(sample_case=main_case).exists() and main_case.workflow_status == "S03"
    assert not ProviderMessage.objects.exists()


def test_a_batch_never_reaches_a_locked_reserve_and_refuses_a_channel_not_set_up(twilio, settings, locked_reserve_case):
    Respondent.objects.create(sample_case=locked_reserve_case, full_name="R", phone="0771111111")
    assert locked_reserve_case not in b.batch_candidates(["SMS"])
    with pytest.raises(b.BatchError, match="WhatsApp isn't set up"):
        b.start_batch(1, user=_user(Role.FIELD_COORDINATOR, "tw_fc3"), channels=["WHATSAPP"])


def test_the_batch_screen_shows_what_each_channel_can_reach_and_the_sms_cost(twilio, main_case):
    _verified(main_case, email="jane@example.org")
    info = _client(_user(Role.FIELD_COORDINATOR, "tw_fc4")).get("/api/v1/invitations/batch/?channels=SMS").data
    assert info["channels"]["SMS"]["configured"] is True and info["channels"]["SMS"]["ready"] == 1
    assert info["channels"]["WHATSAPP"]["configured"] is False and info["channels"]["EMAIL"]["ready"] == 1
    assert info["channels"]["SMS"]["cost_usd_all"] > 0 and info["preview"][0]["mobile"] == "+263 ••• 567"


# --- Automatic reminders -------------------------------------------------------------------------------------------

def _invited(case, days_ago, *, phone="0771234567"):
    _verified(case, phone=phone)
    issue_invitation(case)
    token = case.invitation_tokens.order_by("-issued_at").first()
    token.issued_at = timezone.now() - timedelta(days=days_ago)
    token.save(update_fields=["issued_at"])
    return token


def test_reminders_go_by_sms_until_whatsapp_templates_are_set_up(twilio, settings, main_case):
    _invited(main_case, days_ago=2)
    [log] = dispatch_due_reminders()
    assert log.channel == "SMS" and log.status == MessageStatus.SENT and log.triggered_by is None
    assert "Call 0773943709" in twilio.sent[0]["data"]["Body"]  # the SMS wording, not "reply here"
    assert ProviderMessage.objects.get().message_log_id == log.pk
    assert AuditEvent.objects.filter(action="reminder.sent_automatically").count() == 1
    assert dispatch_due_reminders() == []  # sent once, not every morning


def test_reminders_go_by_whatsapp_when_its_template_is_set_up(twilio, settings, main_case):
    _whatsapp(settings)
    _invited(main_case, days_ago=2)
    [log] = dispatch_due_reminders()
    assert log.channel == "WHATSAPP" and twilio.sent[0]["data"]["ContentSid"] == "HXday2"


def test_no_automatic_reminder_to_a_landline_an_expired_link_or_a_booked_call(twilio, main_case, organisation, stratum):
    from apps.contacts.models import Appointment
    from apps.sampling.services import create_sample_case

    _invited(main_case, days_ago=2, phone="+263 9 75315")
    expired_case = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    token = _invited(expired_case, days_ago=2)
    InvitationToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    booked = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    _invited(booked, days_ago=2)
    Appointment.objects.create(sample_case=booked, scheduled_for=timezone.now() + timedelta(days=1), mode="PHONE", status="REQUESTED")
    assert dispatch_due_reminders() == [] and twilio.sent == []


def test_a_refused_reminder_is_left_for_a_person_and_never_retried(twilio, main_case):
    _invited(main_case, days_ago=2)
    twilio.answers.append((400, {"code": 21610, "message": "unsubscribed"}))
    assert dispatch_due_reminders() == []
    assert MessageLog.objects.get().status == MessageStatus.FAILED
    assert dispatch_due_reminders() == [] and len(twilio.sent) == 1  # not tried again
    [item] = due_follow_ups()
    assert item["auto_failed"] is True and item["sends_automatically"] is False


def test_an_undelivered_reminder_does_not_count_toward_nonresponse(twilio, main_case):
    _invited(main_case, days_ago=8)
    dispatch_due_reminders()  # the Day 7 reminder
    sid = ProviderMessage.objects.get().provider_sid
    params = {"MessageSid": sid, "MessageStatus": "undelivered"}
    _report(params, _sign(params))
    assert exhaust_nonresponse_cases() == []
    assert dispatch_due_reminders() == [] and len(twilio.sent) == 1


def test_follow_ups_say_when_a_reminder_will_go_automatically(twilio, settings, main_case):
    _invited(main_case, days_ago=2)
    assert due_follow_ups()[0]["sends_automatically"] is True
    settings.TWILIO_SMS_FROM = ""
    assert due_follow_ups()[0]["sends_automatically"] is False


# --- Daily caps ----------------------------------------------------------------------------------------------------

def test_the_daily_cap_stops_sending(twilio, settings, main_case):
    settings.TWILIO_SMS_DAILY_MAX = 1
    outbound.send(channel="SMS", number="263771234567", purpose="INVITATION", sms_body="first")
    with pytest.raises(outbound.OutboundError) as exc:
        outbound.send(channel="SMS", number="263771234567", purpose="INVITATION", sms_body="second")
    assert exc.value.code == "daily_limit_reached" and len(twilio.sent) == 1
    _invited(main_case, days_ago=2)
    assert dispatch_due_reminders() == [] and len(twilio.sent) == 1
