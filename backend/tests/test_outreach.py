"""Ask first, then invite (apps/messaging/outreach.py, 2026-10-07). Twilio is a fake requests.post; replies arrive as
signed posts to the incoming-message webhook, the way Twilio sends them. Under test:

- the webhook refuses unsigned or altered posts and ignores Twilio's retries;
- an introduction goes as the approved WhatsApp template, or as an SMS carrying the tap-to-reply WhatsApp link;
- YES issues one invitation and sends its link back in the chat; a second YES issues nothing; a YES when no link can
  be sent goes to a person;
- NO records the refusal (S12 Refused, open invitation revoked) and acknowledges once;
- anything else, "no problem" included, goes to a person with one automatic answer a day; an unknown number never
  touches a case;
- no reply: one reminder, then listed for RAs; an undelivered WhatsApp introduction is re-sent once by SMS;
- Conversations: who sees what, replies only inside WhatsApp's 24 hours; withdrawal erases what they wrote;
- "ask first" batches.
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
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation, validate_token
from apps.messaging import outreach, tasks
from apps.messaging import twilio_client as tw
from apps.messaging.models import InboundMessage, Outreach, OutreachStatus, ProviderMessage
from apps.sampling.services import transition_workflow_status

MOBILE = "263771234567"
INBOUND = "/api/v1/twilio/inbound/"
STATUS = "/api/v1/twilio/status/"


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "CUT-ABFFST", "+15550001111"
    settings.TWILIO_WA_CONTENT_INTRO, settings.TWILIO_WA_CONTENT_INTRO_REMINDER = "HXintro", "HXintroReminder"
    settings.TWILIO_WA_CONTENT_INVITATION = settings.TWILIO_WA_CONTENT_KII_INVITATION = ""
    settings.TWILIO_WA_CONTENT_REMINDER_DAY2 = settings.TWILIO_WA_CONTENT_REMINDER_DAY7 = ""
    settings.TWILIO_SMS_OPT_OUT_LINE = ""
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    settings.INVITATION_EMAIL_PAUSE_SECONDS = 0
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued", "num_segments": "1"}))

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(tasks.handle_inbound_message, "delay", lambda *args: outreach.handle_inbound(*args))
    return sent


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _verified(case, phone="0771234567"):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    Respondent.objects.create(sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD, is_eligible=True, phone=phone)
    return case


def _sign(url, params, token="secret-token"):
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


_sid = iter(range(1000, 9999))


def _reply(body="", *, number=MOBILE, payload="", sid=None, signature=None):
    params = {"MessageSid": sid or f"SMin{next(_sid)}", "From": f"whatsapp:+{number}", "To": "whatsapp:+15550001111", "Body": body}
    if payload:
        params["ButtonPayload"] = payload
    signature = _sign(tw.inbound_url(), params) if signature is None else signature
    return APIClient().post(INBOUND, urlencode(params), content_type="application/x-www-form-urlencoded", HTTP_X_TWILIO_SIGNATURE=signature)


@pytest.fixture
def introduced(twilio, main_case):
    _verified(main_case)
    return outreach.send_introduction(main_case, user=_user(Role.FIELD_COORDINATOR, "out_fc"))


# --- The webhook ---------------------------------------------------------------------------------------------------

def test_an_unsigned_or_altered_reply_is_refused_and_nothing_is_stored(introduced):
    assert _reply("YES", signature="").status_code == 403
    params = {"MessageSid": "SMx", "From": f"whatsapp:+{MOBILE}", "Body": "NO"}
    altered = {**params, "Body": "YES"}
    resp = APIClient().post(INBOUND, urlencode(altered), content_type="application/x-www-form-urlencoded",
                            HTTP_X_TWILIO_SIGNATURE=_sign(tw.inbound_url(), params))
    assert resp.status_code == 403
    assert not InboundMessage.objects.exists() and not InvitationToken.objects.exists()


def test_twilio_retrying_the_same_message_is_ignored(introduced, main_case):
    assert _reply("YES", sid="SMsame").status_code == 200
    assert _reply("YES", sid="SMsame").status_code == 200
    assert InboundMessage.objects.count() == 1 and InvitationToken.objects.filter(sample_case=main_case).count() == 1


# --- The introduction ----------------------------------------------------------------------------------------------

def test_the_introduction_is_the_approved_whatsapp_template_and_changes_nothing_else(introduced, twilio, main_case):
    [data] = twilio
    assert (data["To"], data["ContentSid"]) == (f"whatsapp:+{MOBILE}", "HXintro")
    assert json.loads(data["ContentVariables"]) == {"1": main_case.organisation.name}
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S03" and not InvitationToken.objects.exists()
    assert introduced.status == OutreachStatus.INTRO_SENT and introduced.number_masked == "+263 ••• 567"
    assert MOBILE not in str(AuditEvent.objects.get(action="outreach.introduced").metadata)


def test_without_the_whatsapp_template_it_goes_by_sms_with_the_tap_to_reply_link(twilio, settings, main_case):
    settings.TWILIO_WA_CONTENT_INTRO = ""
    _verified(main_case)
    outreach.send_introduction(main_case, user=None)
    assert twilio[0]["To"] == f"+{MOBILE}" and "https://wa.me/15550001111?text=YES" in twilio[0]["Body"]


def test_no_introduction_without_the_study_whatsapp_number_since_no_reply_could_arrive(twilio, settings, main_case):
    settings.TWILIO_WHATSAPP_FROM = ""
    _verified(main_case)
    with pytest.raises(outreach.OutreachError) as exc:
        outreach.send_introduction(main_case, user=None)
    assert exc.value.code == "not_configured" and twilio == []


def test_a_case_is_introduced_once_and_a_locked_reserve_never(introduced, locked_reserve_case):
    Respondent.objects.create(sample_case=locked_reserve_case, full_name="R", phone="0771111111")
    assert list(outreach.introduction_candidates()) == []
    with pytest.raises(outreach.OutreachError):
        outreach.send_introduction(introduced.sample_case, user=None)


def test_a_contact_ra_introduces_only_their_own_cases(twilio, main_case):
    _verified(main_case)
    mine, other = _user(Role.CONTACT_RA, "out_ra"), _user(Role.CONTACT_RA, "out_other")
    main_case.assigned_ra = mine
    main_case.save(update_fields=["assigned_ra"])
    assert _client(other).post("/api/v1/outreach/", {"sample_id": main_case.sample_id}, format="json").status_code == 403
    assert _client(_user(Role.SUPERVISOR_READONLY, "out_sup")).post("/api/v1/outreach/", {"sample_id": main_case.sample_id}, format="json").status_code == 403
    assert _client(mine).post("/api/v1/outreach/", {"sample_id": main_case.sample_id}, format="json").status_code == 201


# --- YES -------------------------------------------------------------------------------------------------------------

def test_yes_issues_the_invitation_and_sends_its_link_in_the_chat(introduced, twilio, main_case):
    _reply("Yes!")
    [token] = InvitationToken.objects.filter(sample_case=main_case)
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S05" and token.channel == "WHATSAPP"
    reply = twilio[-1]
    assert reply["To"] == f"whatsapp:+{MOBILE}" and "ContentSid" not in reply  # a free-text reply in the chat
    raw = reply["Body"].split("/i/", 1)[1].split()[0]
    assert validate_token(raw).pk == token.pk
    introduced.refresh_from_db()
    assert introduced.status == OutreachStatus.ACCEPTED and introduced.invitation_token_id == token.pk


def test_the_quick_reply_button_counts_and_a_second_yes_issues_nothing(introduced, twilio, main_case):
    _reply("Yes, I'll take part", payload="YES")
    _reply("yes")
    assert InvitationToken.objects.filter(sample_case=main_case).count() == 1
    assert "link is in the message above" in twilio[-1]["Body"]


def test_yes_sends_no_link_when_the_case_can_no_longer_be_invited(introduced, twilio, main_case):
    issue_invitation(main_case, channel="EMAIL")  # someone sent an invitation by another route meanwhile
    _reply("YES")
    assert InvitationToken.objects.filter(sample_case=main_case).count() == 1
    assert "will contact you shortly" in twilio[-1]["Body"]
    assert InboundMessage.objects.get().needs_person is True


# --- NO --------------------------------------------------------------------------------------------------------------

def test_no_records_the_refusal_and_acknowledges_once(introduced, twilio, main_case):
    _reply("No")
    main_case.refresh_from_db()
    introduced.refresh_from_db()
    assert main_case.workflow_status == "S12" and introduced.status == OutreachStatus.DECLINED
    assert "will not contact you again" in twilio[-1]["Body"]
    sent = len(twilio)
    _reply("STOP")
    assert len(twilio) == sent  # no second acknowledgement
    assert AuditEvent.objects.get(action="outreach.declined").metadata["moved_to"] == "S12"


def test_no_after_yes_revokes_the_open_invitation(introduced, main_case):
    _reply("YES")
    _reply("hapana")
    token = InvitationToken.objects.get(sample_case=main_case)
    main_case.refresh_from_db()
    assert token.status == TokenStatus.REVOKED and main_case.workflow_status == "S12"


# --- Anything else ---------------------------------------------------------------------------------------------------

def test_no_problem_is_not_a_refusal_and_goes_to_a_person_with_one_answer_a_day(introduced, twilio, main_case):
    _reply("No problem, who is this?")
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S03"
    message = InboundMessage.objects.get()
    assert message.kind == "OTHER" and message.needs_person and "A member of the research team will reply" in twilio[-1]["Body"]
    sent = len(twilio)
    _reply("Hello?")
    assert len(twilio) == sent  # one automatic answer a day


def test_an_unknown_number_never_touches_a_case(introduced, twilio, main_case):
    _reply("YES", number="263712000000")
    message = InboundMessage.objects.get()
    assert message.outreach is None and message.sample_case is None and message.needs_person
    assert message.from_number == "263712000000" and not InvitationToken.objects.exists()


# --- No reply, and messages that never arrived -----------------------------------------------------------------------

def test_one_reminder_after_three_days_then_listed_for_rras(introduced, twilio, main_case):
    Outreach.objects.filter(pk=introduced.pk).update(intro_sent_at=timezone.now() - timedelta(days=3))
    assert outreach.run_followups()["reminded"] == 1
    assert twilio[-1]["ContentSid"] == "HXintroReminder"
    assert outreach.run_followups()["reminded"] == 0  # once only
    Outreach.objects.filter(pk=introduced.pk).update(reminded_at=timezone.now() - timedelta(days=4))
    assert outreach.run_followups()["no_reply"] == 1
    [item] = outreach.unanswered()
    assert item["sample_id"] == main_case.sample_id and item["status"] == OutreachStatus.NO_REPLY
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S03"


def test_a_late_yes_still_sends_the_link(introduced, main_case):
    Outreach.objects.filter(pk=introduced.pk).update(status=OutreachStatus.NO_REPLY)
    _reply("YES")
    assert InvitationToken.objects.filter(sample_case=main_case).count() == 1


def _report(sid, status):
    params = {"MessageSid": sid, "MessageStatus": status}
    return APIClient().post(STATUS, urlencode(params), content_type="application/x-www-form-urlencoded",
                            HTTP_X_TWILIO_SIGNATURE=_sign(tw.status_callback_url(), params))


def test_an_undelivered_whatsapp_introduction_is_sent_once_by_sms(introduced, twilio):
    intro = ProviderMessage.objects.get()
    _report(intro.provider_sid, "undelivered")
    assert twilio[-1]["To"] == f"+{MOBILE}" and "wa.me" in twilio[-1]["Body"]
    introduced.refresh_from_db()
    assert introduced.sms_fallback_sent
    sms = ProviderMessage.objects.filter(channel="SMS").get()
    _report(sms.provider_sid, "undelivered")
    introduced.refresh_from_db()
    assert introduced.status == OutreachStatus.NOT_DELIVERED and len(twilio) == 2


# --- Conversations ---------------------------------------------------------------------------------------------------

def test_conversations_show_each_ra_only_their_own_cases(introduced, main_case):
    _reply("Who is this?")
    _reply("Hi", number="263712000000")
    ra = _user(Role.CONTACT_RA, "conv_ra")
    assert _client(ra).get("/api/v1/conversations/").json()["results"] == []
    main_case.assigned_ra = ra
    main_case.save(update_fields=["assigned_ra"])
    rows = _client(ra).get("/api/v1/conversations/").json()["results"]
    assert [r["body"] for r in rows] == ["Who is this?"]  # not the unknown number
    assert len(_client(_user(Role.FIELD_COORDINATOR, "conv_fc")).get("/api/v1/conversations/").json()["results"]) == 2


def test_a_reply_goes_only_inside_whatsapps_24_hours_and_supervisor_only_reads(introduced, twilio):
    _reply("Who is this?")
    message = InboundMessage.objects.get()
    fc = _client(_user(Role.FIELD_COORDINATOR, "conv_fc2"))
    sup = _client(_user(Role.SUPERVISOR_READONLY, "conv_sup"))
    assert sup.get("/api/v1/conversations/").status_code == 200
    assert sup.post(f"/api/v1/conversations/{message.pk}/reply/", {"text": "Hi"}, format="json").status_code == 403
    resp = fc.post(f"/api/v1/conversations/{message.pk}/reply/", {"text": "We are from CUT."}, format="json")
    assert resp.status_code == 200 and twilio[-1]["Body"] == "We are from CUT." and resp.json()["needs_person"] is False
    InboundMessage.objects.filter(pk=message.pk).update(received_at=timezone.now() - timedelta(hours=25))
    late = fc.post(f"/api/v1/conversations/{message.pk}/reply/", {"text": "Hello again"}, format="json")
    assert late.status_code == 409 and late.json()["error"]["code"] == "window_closed"


def test_withdrawal_erases_what_they_wrote(introduced, main_case):
    from apps.consent.withdrawal import record_withdrawal

    _reply("Please call me on 0772 000 111")
    record_withdrawal(main_case, reason="Asked to withdraw", recorded_by=_user(Role.FIELD_COORDINATOR, "out_fc3"))
    assert InboundMessage.objects.get().body == ""


# --- Batches -------------------------------------------------------------------------------------------------------

def test_an_ask_first_batch_introduces_cases_without_issuing_invitations(twilio, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    _verified(main_case)
    second = _verified(create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026), phone="0772222222")
    info = _client(_user(Role.FIELD_COORDINATOR, "out_fc4")).get("/api/v1/invitations/batch/").json()
    assert info["introductions"] == {"configured": True, "channel": "WHATSAPP", "ready": 2, "left_today": 250}
    batch = b.start_batch(2, user=_user(Role.FIELD_COORDINATOR, "out_fc5"), mode="INTRO")
    b.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 2 and Outreach.objects.filter(sample_case__in=[main_case, second]).count() == 2
    assert not InvitationToken.objects.exists()
