"""Ask first, then invite -- for KII informants (apps/messaging/outreach.py, PI request 2026-10-14). Twilio is a fake
requests.post; replies arrive as signed posts to the incoming-message webhook, the way Twilio sends them. Under test:

- the KII introduction goes as its own approved template, greeting the named informant and organisation (or the
  organisation alone while no informant is named), and moves nothing;
- YES issues one KII link (PROSPECT -> INVITED) and sends it back in the chat; a second YES issues nothing; a YES
  when the record was invited by hand meanwhile goes to a person; if the link cannot be sent, nothing is kept;
- NO records DECLINED, revokes any open link and acknowledges once;
- only records never invited, with a mobile and no earlier introduction, are introduced; a pending template sends
  the SMS with the reply link instead;
- no reply: one reminder, then listed to phone; an undelivered WhatsApp introduction is re-sent once by SMS;
- an Outreach belongs to exactly one case or KII record (database constraint); a Main-400 introduction still works;
- the KII batch's "ask first" mode and who may send.
"""

import base64
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.kii import batch as kb
from apps.kii.models import KIIInvitationTokenStatus, KIIStatus
from apps.kii.services import create_kii_record, issue_kii_invitation, validate_kii_token
from apps.messaging import outreach, tasks
from apps.messaging import twilio_client as tw
from apps.messaging.models import InboundMessage, Outreach, OutreachStatus, ProviderMessage

pytestmark = pytest.mark.django_db

MOBILE = "263771234567"
INBOUND = "/api/v1/twilio/inbound/"
STATUS = "/api/v1/twilio/status/"


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "CUT-ABFFST", "+15550001111"
    settings.TWILIO_WA_CONTENT_INTRO, settings.TWILIO_WA_CONTENT_INTRO_REMINDER = "HXintro", "HXintroReminder"
    settings.TWILIO_WA_CONTENT_KII_INTRO, settings.TWILIO_WA_CONTENT_KII_INTRO_REMINDER = "HXkiiIntro", "HXkiiIntroReminder"
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


def _record(name="Tendai Moyo", *, phone="0771234567", status=KIIStatus.PROSPECT, pool="CORE_60"):
    return create_kii_record(participant_name=name, participant_role="Director", stakeholder_category="Bank",
                             status=status, phone=phone, metadata={"organisation_name": "Agri Bank", "pool": pool})


def _sign(url, params, token="secret-token"):
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


_sid = iter(range(1000, 9999))


def _reply(body="", *, number=MOBILE, payload=""):
    params = {"MessageSid": f"SMin{next(_sid)}", "From": f"whatsapp:+{number}", "To": "whatsapp:+15550001111", "Body": body}
    if payload:
        params["ButtonPayload"] = payload
    return APIClient().post(INBOUND, urlencode(params), content_type="application/x-www-form-urlencoded",
                            HTTP_X_TWILIO_SIGNATURE=_sign(tw.inbound_url(), params))


def _report(sid, status):
    params = {"MessageSid": sid, "MessageStatus": status}
    return APIClient().post(STATUS, urlencode(params), content_type="application/x-www-form-urlencoded",
                            HTTP_X_TWILIO_SIGNATURE=_sign(tw.status_callback_url(), params))


@pytest.fixture
def introduced(twilio):
    record = _record()
    return outreach.send_kii_introduction(record, user=_user(Role.KII_RA, "kout_ra"))


# --- The introduction ----------------------------------------------------------------------------------------------

def test_the_introduction_is_the_kii_template_greeting_the_informant_and_changes_nothing_else(introduced, twilio):
    [data] = twilio
    assert (data["To"], data["ContentSid"]) == (f"whatsapp:+{MOBILE}", "HXkiiIntro")
    assert json.loads(data["ContentVariables"]) == {"1": "Tendai Moyo (Agri Bank)"}
    record = introduced.kii_record
    record.refresh_from_db()
    assert record.status == KIIStatus.PROSPECT and not record.invitation_tokens.exists()
    assert introduced.status == OutreachStatus.INTRO_SENT and introduced.sample_case is None
    shown = ProviderMessage.objects.get().body
    assert "Good day, Tendai Moyo (Agri Bank)." in shown and "about 30 minutes" in shown  # Communications shows the words
    assert MOBILE not in str(AuditEvent.objects.get(action="outreach.introduced").metadata)


def test_an_unnamed_record_is_greeted_by_its_organisation(twilio):
    record = _record("Agri Bank (contact not yet identified)")
    outreach.send_kii_introduction(record, user=None)
    assert json.loads(twilio[0]["ContentVariables"]) == {"1": "Agri Bank"}


def test_only_a_record_never_invited_with_a_mobile_and_no_earlier_introduction_is_introduced(twilio):
    invited = _record(status=KIIStatus.INVITED)
    landline = _record(phone="+263 242 703961")
    open_link = _record()
    issue_kii_invitation(open_link)
    open_link.status = KIIStatus.PROSPECT
    open_link.save(update_fields=["status"])
    for record, code in ((invited, "not_ready"), (landline, "no_mobile"), (open_link, "not_ready")):
        with pytest.raises(outreach.OutreachError) as exc:
            outreach.send_kii_introduction(record, user=None)
        assert exc.value.code == code, record
    once = _record(phone="0772000111")
    outreach.send_kii_introduction(once, user=None)
    with pytest.raises(outreach.OutreachError):
        outreach.send_kii_introduction(once, user=None)
    assert len(twilio) == 1


def test_while_meta_has_the_kii_introduction_pending_it_goes_by_sms_with_the_reply_link(twilio, monkeypatch):
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [{"sid": "HXkiiIntro", "status": "pending"}])
    sent = outreach.send_kii_introduction(_record(), user=None)
    assert sent.channel == "SMS" and twilio[0]["To"] == f"+{MOBILE}" and "wa.me/15550001111" in twilio[0]["Body"]
    assert "key informant interview" in twilio[0]["Body"]


# --- Replies -------------------------------------------------------------------------------------------------------

def test_yes_issues_the_kii_link_and_sends_it_in_the_chat(introduced, twilio):
    _reply("", payload="YES")
    record = introduced.kii_record
    record.refresh_from_db()
    introduced.refresh_from_db()
    token = record.invitation_tokens.get()
    assert record.status == KIIStatus.INVITED and introduced.status == OutreachStatus.ACCEPTED
    assert introduced.kii_invitation_token_id == token.pk and token.channel == "WHATSAPP"
    link_message = twilio[-1]["Body"]
    raw = link_message.split("/ki/")[1].split()[0]
    assert validate_kii_token(raw).kii_record_id == record.pk  # the link in the chat opens this record's own invitation
    assert InboundMessage.objects.get().kii_record_id == record.pk
    _reply("Yes")  # a second YES issues nothing new
    assert record.invitation_tokens.count() == 1 and "above" in twilio[-1]["Body"]


def test_yes_after_the_record_was_invited_by_hand_goes_to_a_person(introduced, twilio):
    issue_kii_invitation(introduced.kii_record)
    _reply("YES")
    assert introduced.kii_record.invitation_tokens.count() == 1
    assert InboundMessage.objects.get().needs_person is True
    assert AuditEvent.objects.filter(action="outreach.accept_not_sent").exists()


def test_if_the_link_cannot_be_sent_nothing_is_kept(introduced, twilio, settings):
    settings.TWILIO_WHATSAPP_DAILY_MAX = 1  # the introduction used today's only WhatsApp message
    _reply("YES")
    record = introduced.kii_record
    record.refresh_from_db()
    introduced.refresh_from_db()
    assert record.status == KIIStatus.PROSPECT and not record.invitation_tokens.exists()
    assert introduced.status == OutreachStatus.INTRO_SENT and InboundMessage.objects.get().needs_person is True


def test_no_records_declined_revokes_any_open_link_and_acknowledges_once(introduced, twilio):
    _, _, token = issue_kii_invitation(introduced.kii_record)
    _reply("No")
    record = introduced.kii_record
    record.refresh_from_db()
    token.refresh_from_db()
    introduced.refresh_from_db()
    assert record.status == KIIStatus.DECLINED and introduced.status == OutreachStatus.DECLINED
    assert token.status == KIIInvitationTokenStatus.REVOKED
    acknowledgements = len(twilio)
    _reply("STOP")
    assert len(twilio) == acknowledgements


def test_a_question_goes_to_a_person(introduced, twilio):
    _reply("Who gave you my number?")
    message = InboundMessage.objects.get()
    assert message.needs_person and message.kii_record_id == introduced.kii_record_id
    assert introduced.kii_record.invitation_tokens.count() == 0


# --- No reply, and introductions that never arrived ----------------------------------------------------------------

def test_one_reminder_after_three_days_then_listed_to_phone(introduced, twilio):
    Outreach.objects.filter(pk=introduced.pk).update(intro_sent_at=timezone.now() - timedelta(days=3))
    assert outreach.run_followups()["reminded"] == 1
    assert twilio[-1]["ContentSid"] == "HXkiiIntroReminder"
    assert outreach.run_followups()["reminded"] == 0
    Outreach.objects.filter(pk=introduced.pk).update(reminded_at=timezone.now() - timedelta(days=4))
    assert outreach.run_followups()["no_reply"] == 1
    [item] = outreach.kii_unanswered()
    assert item["kii_id"] == introduced.kii_record.kii_id and item["status"] == OutreachStatus.NO_REPLY
    assert outreach.unanswered() == []  # the Main-400 Follow-ups list is unchanged
    ra = _client(_user(Role.KII_RA, "kout_ra2"))
    assert ra.get("/api/v1/kii-outreach/unanswered/").json()["count"] == 1


def test_an_undelivered_whatsapp_introduction_is_sent_once_by_sms(introduced, twilio):
    _report(ProviderMessage.objects.get().provider_sid, "undelivered")
    assert twilio[-1]["To"] == f"+{MOBILE}" and "wa.me" in twilio[-1]["Body"]
    introduced.refresh_from_db()
    assert introduced.sms_fallback_sent
    _report(ProviderMessage.objects.get(channel="SMS").provider_sid, "undelivered")
    introduced.refresh_from_db()
    assert introduced.status == OutreachStatus.NOT_DELIVERED and len(twilio) == 2


# --- One target per introduction, and Main-400 unchanged -----------------------------------------------------------

def test_an_introduction_belongs_to_exactly_one_case_or_record(main_case, twilio):
    record = _record()
    base = {"channel": "WHATSAPP", "number_hash": "x", "number_masked": "x", "intro_sent_at": timezone.now()}
    for bad in ({"sample_case": main_case, "kii_record": record}, {}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Outreach.objects.create(**base, **bad)


def test_a_reply_goes_to_the_latest_introduction_for_that_number(main_case, twilio):
    from apps.contacts.models import Respondent, RoleCategory
    from apps.sampling.services import transition_workflow_status

    for status in ("S01", "S02", "S03"):
        transition_workflow_status(main_case, status)
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
                              is_eligible=True, phone="0771234567")
    outreach.send_introduction(main_case, user=None)
    kii = outreach.send_kii_introduction(_record(), user=None)  # the same person, asked again for an interview
    _reply("YES")
    kii.refresh_from_db()
    assert kii.status == OutreachStatus.ACCEPTED and not main_case.invitation_tokens.exists()


# --- Batches and permissions ---------------------------------------------------------------------------------------

def test_an_ask_first_batch_introduces_records_never_invited_core_60_first(twilio):
    reserve = _record(pool="RESERVE_30", phone="0772000111")
    core = _record(pool="CORE_60", phone="0772000222")
    _record(status=KIIStatus.INVITED, phone="0772000333")
    info = kb.summary(("EMAIL",), kb.GROUPS)["introductions"]
    assert info["configured"] and info["channel"] == "WHATSAPP" and info["ready"] == 2
    batch = kb.start_batch(1, user=_user(Role.FIELD_COORDINATOR, "kout_fc"), intro=True)
    kb.run_batch(batch)
    assert batch.sent == 1 and batch.results[0]["kii_id"] == core.kii_id
    assert Outreach.objects.get().kii_record_id == core.pk and not Outreach.objects.filter(kii_record=reserve).exists()


def test_who_may_ask_first(twilio):
    record = _record()
    for role in ("CONTACT_RA", "ANALYST", "DOC_RA"):
        resp = _client(_user(role, f"kout_{role.lower()}")).post("/api/v1/kii-outreach/", {"kii_id": record.kii_id}, format="json")
        assert resp.status_code == 403, role
    sup = _client(_user(Role.SUPERVISOR_READONLY, "kout_sup"))
    assert sup.get(f"/api/v1/kii-outreach/?kii_id={record.kii_id}").status_code == 200
    assert sup.post("/api/v1/kii-outreach/", {"kii_id": record.kii_id}, format="json").status_code == 403
    ra = _client(_user(Role.KII_RA, "kout_ra3"))
    resp = ra.post("/api/v1/kii-outreach/", {"kii_id": record.kii_id}, format="json")
    assert resp.status_code == 201 and resp.json()["status"] == "INTRO_SENT"
    rows = ra.get(f"/api/v1/kii-outreach/?kii_id={record.kii_id}").json()
    assert rows["intro_channel"] == "WHATSAPP" and rows["results"][0]["status_label"] == "Asked"
