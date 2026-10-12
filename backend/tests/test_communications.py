"""Communications (apps/messaging/communications.py, mailbox.py, 2026-10-12): one place to message respondents and key
informants and follow every message. Twilio is a fake requests.post; the study mailbox is a fake IMAP server. Under test:

- what is sent is kept without the personal link or code (a link works like a password);
- email: a sent email is recorded, a bounce marks it not delivered;
- the mailbox: only email from or to someone on a case or KII record is copied in; an answer to a portal email is
  matched by In-Reply-To before the address; the mailbox is only ever read (EXAMINE, BODY.PEEK, never STORE); nothing
  is copied twice; a copy of the portal's own email in the sent folder is skipped; links in what is copied are taken out;
- writing a message refuses forbidden words (AGENTS.md rule 2), a locked Reserve (rule 4), a withdrawn participant,
  WhatsApp outside 24 hours, a number or address not on the record, and a read-only role;
- who sees what: a Contact RA only their own cases, a KII RA only KII records, unknown numbers PI and FC only;
- a WhatsApp message from a recorded number with no introduction lands on that case;
- the conversation shows invitations sent by hand, the link opened, and follow-ups marked sent;
- withdrawal erases the text of messages both ways.
"""

import email.message
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentRecord, ConsentType
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.messages import email_invitation
from apps.invitations.services import issue_invitation, validate_token
from apps.kii.services import create_kii_record
from apps.messaging import communications as comms
from apps.messaging import mailbox, outbound, outreach, tasks
from apps.messaging import twilio_client as tw
from apps.messaging.hashing import email_hash
from apps.messaging.models import (
    InboundMessage,
    MailboxCursor,
    MessageChannel,
    MessageProvider,
    MessagePurpose,
    ProviderMessage,
    ProviderStatus,
)

THREADS = "/api/v1/communications/threads/"
PERSON_EMAIL = "jane@farmco.co.zw"


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    settings.TWILIO_WA_CONTENT_INVITATION = "HXinv"
    settings.TWILIO_WA_CONTENT_INTRO = settings.TWILIO_WA_CONTENT_INTRO_REMINDER = ""
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued"}))

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [])
    monkeypatch.setattr(tasks.handle_inbound_message, "delay", lambda *args: outreach.handle_inbound(*args))
    return sent


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def pi(db):
    return _user(Role.PI_ADMIN, "com_pi")


@pytest.fixture
def person(main_case):
    return Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
                                     is_eligible=True, phone="0771234567", email=PERSON_EMAIL)


def _kii():
    return create_kii_record(participant_name="Tendai Moyo", participant_role="Head of Agribusiness",
                             stakeholder_category="Bank, DFI & MFI", metadata={"organisation_name": "CBZ Bank"})


def _whatsapp_in(case, body="Hello, I have a question", number="263771234567", minutes_ago=0):
    message = InboundMessage.objects.create(
        channel=MessageChannel.WHATSAPP, provider_sid=f"SMin-{InboundMessage.objects.count()}", sample_case=case,
        number_hash=outreach.number_hash(number), from_masked=tw.mask(number), body=body, needs_person=True)
    if minutes_ago:
        InboundMessage.objects.filter(pk=message.pk).update(received_at=timezone.now() - timedelta(minutes=minutes_ago))
    return message


# --- What is kept of what was sent ---------------------------------------------------------------------------------

def test_an_emailed_invitation_is_recorded_without_its_link_or_code(person, main_case, pi):
    raw, code, token = issue_invitation(main_case, channel="EMAIL", issued_by=pi)
    link = f"https://research.agribizframework.com/i/{raw}"
    email_invitation(token, link=link, manual_code=code, user=pi)
    sent = ProviderMessage.objects.get(channel=MessageChannel.EMAIL)
    assert raw in mail.outbox[0].body and code in mail.outbox[0].body  # the respondent gets the real link
    assert raw not in sent.body and code not in sent.body and "[personal link]" in sent.body and "[code]" in sent.body
    assert (sent.status, sent.provider, sent.invitation_token) == (ProviderStatus.SENT, MessageProvider.SMTP, token)
    assert mail.outbox[0].extra_headers["Message-ID"] == sent.provider_sid


def test_a_whatsapp_template_keeps_the_portals_wording_without_the_link(twilio, main_case):
    link, code = "https://research.agribizframework.com/i/" + "x" * 43, "AB12CD34"
    message = outbound.send(channel=MessageChannel.WHATSAPP, number="263771234567", purpose=MessagePurpose.INVITATION,
                            wa_content="HXinv", record_text=f"Your link {link} and code {code}", redact_link=link,
                            redact_code=code, sample_case=main_case)
    assert message.body == "Your link [personal link] and code [code]"
    assert message.to_hash == outreach.number_hash("263771234567")


def test_a_refused_email_is_recorded_as_failed_and_still_raised(person, main_case, monkeypatch):
    from smtplib import SMTPException

    monkeypatch.setattr("django.core.mail.EmailMessage.send", Mock(side_effect=SMTPException("refused")))
    with pytest.raises(SMTPException):
        outbound.send_email(to=PERSON_EMAIL, subject="Hi", body="Hello", purpose=MessagePurpose.MESSAGE, sample_case=main_case)
    assert ProviderMessage.objects.get().status == ProviderStatus.FAILED


# --- The study mailbox ---------------------------------------------------------------------------------------------

def _email(*, sender, to="abffst.research@gmail.com", subject="Re: ABF-FST research study", body="Thanks, happy to help.",
           message_id=None, in_reply_to="", headers=None, date="Mon, 12 Oct 2026 10:00:00 +0200") -> bytes:
    msg = email.message.EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg["Message-ID"] = message_id or f"<{abs(hash((sender, subject, body)))}@mail.example>"
    msg["Date"] = date
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    for key, value in (headers or {}).items():
        msg[key] = value
    msg.set_content(body)
    return msg.as_bytes()


class FakeIMAP:
    """Answers like imaplib.IMAP4_SSL for the commands mailbox.py uses, and records every command."""

    def __init__(self, folders: dict, validity=7):
        self.folders, self.validity, self.commands, self.selected = folders, validity, [], None

    def select(self, mailbox_name, readonly=False):
        self.commands.append(("SELECT", mailbox_name, readonly))
        self.selected = mailbox_name.strip('"')
        return "OK", [str(len(self.folders.get(self.selected, []))).encode()]

    def response(self, code):
        return code, [str(self.validity).encode()]

    def uid(self, command, *args):
        self.commands.append((command.upper(), *args))
        messages = dict(self.folders.get(self.selected, []))
        if command.upper() == "SEARCH":
            criteria = args[-1]
            uids = sorted(messages)
            if criteria.startswith("UID "):
                floor = int(criteria.split()[1].split(":")[0]) - 1
                uids = [u for u in uids if u > floor] or uids[-1:]  # IMAP answers "n:*" with the last message
            return "OK", [" ".join(map(str, uids)).encode()]
        if command.upper() == "FETCH":
            spec, out = args[1], []
            for uid in map(int, args[0].split(",")):
                raw = messages[uid]
                payload = raw.split(b"\n\n", 1)[0] + b"\n\n" if "HEADER.FIELDS" in spec else raw
                out += [(f"{uid} (UID {uid} BODY[] {{{len(payload)}}}".encode(), payload), b")"]
            return "OK", out
        raise AssertionError(f"unexpected IMAP command {command}")

    def store(self, *args):
        self.commands.append(("STORE", *args))
        raise AssertionError("the mailbox must never be changed")

    def logout(self):
        self.commands.append(("LOGOUT",))


@pytest.fixture
def imap_on(settings):
    settings.EMAIL_IMAP_HOST, settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD = "imap.example", "study@x", "pw"
    settings.EMAIL_INBOX_FOLDER, settings.EMAIL_SENT_FOLDER = "INBOX", "[Gmail]/Sent Mail"


def test_only_email_from_someone_on_a_record_is_copied_in_and_the_rest_is_never_read(imap_on, person, main_case):
    fake = FakeIMAP({"INBOX": [(1, _email(sender=f"Jane Doe <{PERSON_EMAIL}>")),
                               (2, _email(sender="newsletter@shop.example", body="Big sale"))]})
    assert mailbox.sync_mailbox(connect=lambda: fake) == {"INBOX": 1, "[Gmail]/Sent Mail": 0}
    stored = InboundMessage.objects.get()
    assert (stored.sample_case, stored.channel, stored.needs_person) == (main_case, MessageChannel.EMAIL, True)
    assert stored.body == "Thanks, happy to help." and stored.from_masked == "j***@farmco.co.zw"
    full_fetches = [c for c in fake.commands if c[0] == "FETCH" and "BODY.PEEK[]" in c[2]]
    assert [c[1] for c in full_fetches] == ["1"]  # the unknown sender's email was never opened


def test_the_mailbox_is_only_ever_read(imap_on, person):
    fake = FakeIMAP({"INBOX": [(1, _email(sender=PERSON_EMAIL))], "[Gmail]/Sent Mail": []})
    mailbox.sync_mailbox(connect=lambda: fake)
    assert all(c[2] is True for c in fake.commands if c[0] == "SELECT")  # EXAMINE, never SELECT read-write
    assert all("BODY.PEEK" in c[2] for c in fake.commands if c[0] == "FETCH")  # never marks anything read
    assert not [c for c in fake.commands if c[0] == "STORE"]


def test_an_answer_to_a_portal_email_is_matched_by_in_reply_to_before_the_address(imap_on, person, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    other = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    Respondent.objects.create(sample_case=other, full_name="Jane again", email=PERSON_EMAIL)  # same address, two cases
    sent = outbound.send_email(to=PERSON_EMAIL, subject="Hello", body="Hi", purpose=MessagePurpose.MESSAGE, sample_case=main_case)
    fake = FakeIMAP({"INBOX": [(1, _email(sender="assistant@farmco.co.zw", in_reply_to=sent.provider_sid))]})
    mailbox.sync_mailbox(connect=lambda: fake)
    assert InboundMessage.objects.get().sample_case == main_case  # an unknown address, but it answers our email


def test_nothing_is_copied_twice_and_new_mail_is_picked_up(imap_on, person):
    folders = {"INBOX": [(1, _email(sender=PERSON_EMAIL, body="First"))]}
    mailbox.sync_mailbox(connect=lambda: FakeIMAP(folders))
    mailbox.sync_mailbox(connect=lambda: FakeIMAP(folders))
    assert InboundMessage.objects.count() == 1 and MailboxCursor.objects.get(folder="INBOX").last_uid == 1
    folders["INBOX"].append((2, _email(sender=PERSON_EMAIL, body="Second")))
    mailbox.sync_mailbox(connect=lambda: FakeIMAP(folders))
    assert InboundMessage.objects.count() == 2


def test_a_bounce_marks_the_portal_email_not_delivered_and_is_not_kept(imap_on, person, main_case):
    sent = outbound.send_email(to=PERSON_EMAIL, subject="Hello", body="Hi", purpose=MessagePurpose.MESSAGE, sample_case=main_case)
    bounce = _email(sender="Mail Delivery Subsystem <mailer-daemon@googlemail.com>", subject="Delivery Status Notification",
                    body="Address not found", headers={"X-Failed-Recipients": PERSON_EMAIL})
    mailbox.sync_mailbox(connect=lambda: FakeIMAP({"INBOX": [(1, bounce)]}))
    sent.refresh_from_db()
    assert sent.status == ProviderStatus.UNDELIVERED and not InboundMessage.objects.exists()


def test_the_sent_folder_adds_what_the_team_wrote_in_gmail_but_skips_the_portals_own(imap_on, person, main_case):
    portal = outbound.send_email(to=PERSON_EMAIL, subject="From the portal", body="Hi", purpose=MessagePurpose.MESSAGE,
                                 sample_case=main_case)
    gmail = _email(sender="abffst.research@gmail.com", to=PERSON_EMAIL, subject="Your link",
                   body="Here it is: https://research.agribizframework.com/i/" + "A" * 43 + " code QWER1234")
    copy = _email(sender="abffst.research@gmail.com", to=PERSON_EMAIL, message_id=portal.provider_sid)
    mailbox.sync_mailbox(connect=lambda: FakeIMAP({"INBOX": [], "[Gmail]/Sent Mail": [(1, gmail), (2, copy)]}))
    written = ProviderMessage.objects.get(provider=MessageProvider.GMAIL_SENT)
    assert written.sample_case == main_case and ProviderMessage.objects.count() == 2
    assert "A" * 43 not in written.body and "QWER1234" not in written.body and "[personal link]" in written.body


def test_an_old_invitation_email_found_in_the_sent_folder_is_shown_once_as_the_invitation(imap_on, pi, person, main_case):
    from apps.audit.utils import log_action

    raw, _, token = issue_invitation(main_case, channel="EMAIL", issued_by=pi)
    log_action("invitation.emailed", token, {"sample_id": main_case.sample_id})  # as sent before 12 Oct: no record kept
    sent_at = timezone.now() - timedelta(days=3)  # long before the sync reads it
    AuditEvent.objects.filter(action="invitation.emailed").update(created_at=sent_at)
    # Django's own emails date themselves "-0000" (no time zone): exactly what the portal's old invitations carry.
    copy = _email(sender="abffst.research@gmail.com", to=PERSON_EMAIL, subject="Invitation: ABF-FST research study",
                  body=f"Your personal link: https://research.agribizframework.com/i/{raw}",
                  date=sent_at.strftime("%a, %d %b %Y %H:%M:%S -0000"))
    mailbox.sync_mailbox(connect=lambda: FakeIMAP({"INBOX": [], "[Gmail]/Sent Mail": [(1, copy)]}))
    items = _client(pi).get(f"{THREADS}main/{main_case.pk}/").json()["items"]
    sent = [i for i in items if i["type"] == "out"]
    assert [i["purpose_label"] for i in sent] == ["Invitation (copy from the study mailbox)"]
    assert not [i for i in items if i["type"] == "event" and "emailed from the study address" in i["text"]]
    assert raw not in sent[0]["body"]


def test_a_quoted_invitation_in_a_reply_loses_its_link(imap_on, person):
    body = "Yes please.\n\nOn Mon, 5 Oct 2026, ABF-FST wrote:\n> Open https://research.agribizframework.com/i/" + "b" * 43
    mailbox.sync_mailbox(connect=lambda: FakeIMAP({"INBOX": [(1, _email(sender=PERSON_EMAIL, body=body))]}))
    assert "b" * 43 not in InboundMessage.objects.get().body


def test_a_reply_dated_without_a_time_zone_is_kept_with_its_own_date(imap_on, person):
    reply = _email(sender=PERSON_EMAIL, date="Sat, 03 Oct 2026 12:55:57 -0000")
    mailbox.sync_mailbox(connect=lambda: FakeIMAP({"INBOX": [(1, reply)]}))
    assert InboundMessage.objects.get().sent_at.isoformat() == "2026-10-03T12:55:57+00:00"


def test_the_mailbox_is_left_alone_when_not_set_up(settings, person):
    settings.EMAIL_IMAP_HOST = ""
    assert "skipped" in mailbox.sync_mailbox(connect=lambda: pytest.fail("must not connect"))


# --- Writing a message ---------------------------------------------------------------------------------------------

def _send(user, case, **data):
    return _client(user).post(f"{THREADS}main/{case.pk}/send/", data, format="json")


def test_an_email_written_here_goes_to_the_recorded_address_as_a_reply(pi, person, main_case):
    InboundMessage.objects.create(channel=MessageChannel.EMAIL, provider_sid="<their@mail>", sample_case=main_case,
                                  number_hash=email_hash(PERSON_EMAIL), from_masked="j***", subject="Question", needs_person=True)
    resp = _send(pi, main_case, channel="EMAIL", recipient=PERSON_EMAIL, subject="Re: Question", text="Happy to explain.")
    assert resp.status_code == 201, resp.json()
    assert mail.outbox[0].to == [PERSON_EMAIL] and mail.outbox[0].extra_headers["In-Reply-To"] == "<their@mail>"
    assert ProviderMessage.objects.get().purpose == MessagePurpose.MESSAGE
    assert not InboundMessage.objects.filter(needs_person=True).exists()  # answering deals with it
    assert AuditEvent.objects.get(action="communication.sent").metadata["recipient"] == "j***@farmco.co.zw"


@pytest.mark.parametrize("text", ["Your loan is approved", "We guarantee nothing", "Your credit rating improves"])
def test_words_a_respondent_must_never_see_are_refused(pi, person, main_case, text):
    resp = _send(pi, main_case, channel="EMAIL", recipient=PERSON_EMAIL, text=text)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "blocked_phrase"
    assert not mail.outbox


def test_whatsapp_text_only_inside_24_hours_of_their_message(twilio, pi, person, main_case):
    resp = _send(pi, main_case, channel="WHATSAPP", recipient="263771234567", text="Hello")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "window_closed" and not twilio
    _whatsapp_in(main_case, minutes_ago=60 * 25)
    assert _send(pi, main_case, channel="WHATSAPP", recipient="263771234567", text="Hello").status_code == 409
    _whatsapp_in(main_case, minutes_ago=30)
    assert _send(pi, main_case, channel="WHATSAPP", recipient="263771234567", text="Hello").status_code == 201
    assert twilio[-1]["Body"] == "Hello" and twilio[-1]["To"] == "whatsapp:+263771234567"


def test_only_a_recorded_number_or_address_can_be_written_to(pi, person, main_case):
    resp = _send(pi, main_case, channel="EMAIL", recipient="someone@else.example", text="Hello")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "unknown_recipient" and not mail.outbox


def test_a_locked_reserve_is_never_written_to(pi, locked_reserve_case):
    Respondent.objects.create(sample_case=locked_reserve_case, full_name="R", email=PERSON_EMAIL)
    resp = _send(pi, locked_reserve_case, channel="EMAIL", recipient=PERSON_EMAIL, text="Hello")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "not_contactable" and not mail.outbox


def test_a_participant_who_withdrew_is_not_written_to(pi, person, main_case):
    ConsentRecord.objects.create(sample_case=main_case, consent_type=ConsentType.PARTICIPATION, information_sheet_version="1",
                                 decision=ConsentDecision.WITHDRAWN, method=ConsentMethod.VERBAL_RA_RECORDED,
                                 timestamp=timezone.now())
    resp = _send(pi, main_case, channel="EMAIL", recipient=PERSON_EMAIL, text="Hello")
    assert resp.status_code == 409 and not mail.outbox


def test_the_supervisor_reads_but_cannot_send(person, main_case):
    supervisor = _user(Role.SUPERVISOR_READONLY, "com_sup")
    assert _client(supervisor).get(f"{THREADS}main/{main_case.pk}/").status_code == 200
    assert _send(supervisor, main_case, channel="EMAIL", recipient=PERSON_EMAIL, text="Hello").status_code == 403
    assert not mail.outbox


# --- Who sees what -------------------------------------------------------------------------------------------------

def test_a_contact_ra_sees_only_their_own_cases_and_never_kii(person, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    ra, other_ra = _user(Role.CONTACT_RA, "com_ra"), _user(Role.CONTACT_RA, "com_ra2")
    other = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    main_case.assigned_ra, other.assigned_ra = ra, other_ra
    main_case.save(update_fields=["assigned_ra"])
    other.save(update_fields=["assigned_ra"])
    record = _kii()
    for case in (main_case, other):
        _whatsapp_in(case)
    InboundMessage.objects.create(channel=MessageChannel.EMAIL, provider_sid="<k@x>", kii_record=record, number_hash="h",
                                  from_masked="t***", needs_person=True)
    rows = _client(ra).get(THREADS).json()["results"]
    assert [(r["kind"], r["id"]) for r in rows] == [("main", main_case.pk)]
    assert _client(ra).get(f"{THREADS}main/{other.pk}/").status_code == 404
    assert _client(ra).get(f"{THREADS}kii/{record.pk}/").status_code == 404


def test_a_kii_ra_sees_only_kii_records(person, main_case):
    record = _kii()
    _whatsapp_in(main_case)
    InboundMessage.objects.create(channel=MessageChannel.EMAIL, provider_sid="<k@x>", kii_record=record, number_hash="h",
                                  from_masked="t***", needs_person=True)
    kii_ra = _user(Role.KII_RA, "com_kii")
    rows = _client(kii_ra).get(THREADS).json()["results"]
    assert [(r["kind"], r["id"]) for r in rows] == [("kii", record.pk)]
    assert _client(kii_ra).get(f"{THREADS}main/{main_case.pk}/").status_code == 404


def test_unknown_numbers_are_for_the_pi_and_coordinator_only(pi, db):
    InboundMessage.objects.create(provider_sid="SMunknown", number_hash="h", from_masked="+263 ••• 999", from_number="263770000999",
                                  body="Who is this?", needs_person=True)
    assert len(_client(pi).get("/api/v1/communications/unknown/").json()["results"]) == 1
    assert _client(_user(Role.CONTACT_RA, "com_ra3")).get("/api/v1/communications/unknown/").json()["results"] == []
    assert _client(_user(Role.KII_RA, "com_kii2")).get("/api/v1/communications/unknown/").json()["results"] == []


def test_roles_with_no_contact_work_are_refused(db):
    for role in (Role.ANALYST, Role.QUAN_QA_RA, Role.DOCUMENTARY_RA):
        assert _client(_user(role, f"com_{role.lower()}")).get(THREADS).status_code == 403


# --- Messages arriving, and the conversation -----------------------------------------------------------------------

def test_a_whatsapp_message_from_a_recorded_number_lands_on_its_case(twilio, person, main_case):
    from tests.test_outreach import _reply

    assert _reply("Good morning, is this the CUT study?").status_code == 200
    message = InboundMessage.objects.get()
    assert message.sample_case == main_case and message.from_number == "" and message.needs_person


def test_the_conversation_shows_hand_sent_invitations_and_the_link_opened(pi, person, main_case):
    from apps.sampling.services import transition_workflow_status

    for status in ("S01", "S02", "S03"):
        transition_workflow_status(main_case, status)
    raw, _, token = issue_invitation(main_case, channel="WHATSAPP", issued_by=pi)
    validate_token(raw)
    token.refresh_from_db()
    assert token.first_opened_at is not None
    texts = [i["text"] for i in _client(pi).get(f"{THREADS}main/{main_case.pk}/").json()["items"] if i["type"] == "event"]
    assert any("sent by hand on WhatsApp" in t for t in texts) and "Opened the invitation link" in texts


def test_the_list_puts_waiting_conversations_first_and_filters_them(pi, person, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    quiet = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    Respondent.objects.create(sample_case=quiet, full_name="Q", email="q@x.example")
    outbound.send_email(to="q@x.example", subject="Hi", body="Hi", purpose=MessagePurpose.MESSAGE, sample_case=quiet)
    _whatsapp_in(main_case, minutes_ago=600)
    rows = _client(pi).get(THREADS).json()["results"]
    assert [r["id"] for r in rows] == [main_case.pk, quiet.pk] and rows[0]["waiting"]
    assert [r["id"] for r in _client(pi).get(THREADS + "?show=waiting").json()["results"]] == [main_case.pk]
    assert [r["id"] for r in _client(pi).get(THREADS + "?channel=EMAIL").json()["results"]] == [quiet.pk]


def test_withdrawal_erases_the_text_both_ways(pi, person, main_case):
    from apps.consent.withdrawal import record_withdrawal

    outbound.send_email(to=PERSON_EMAIL, subject="Hello", body="Private words", purpose=MessagePurpose.MESSAGE, sample_case=main_case)
    _whatsapp_in(main_case, body="My private reply")
    record_withdrawal(main_case, reason="Asked to withdraw", recorded_by=pi)
    assert ProviderMessage.objects.get().body == "" and ProviderMessage.objects.get().subject == ""
    assert InboundMessage.objects.get().body == ""
