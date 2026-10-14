"""WhatsApp attachments and invitation codes (apps/messaging/media.py, 2026-10-14). Twilio is faked: requests.post for
sending, and media.requests.get for listing and downloading media. Under test:

- a voice note, picture or shared contact is copied into private storage; a shared contact's name and number are read;
  a file over the size cap is refused with a reason, never half-kept; a message keeps its reply even if media fails;
- an attachment opens only for someone who may see that conversation (Contact RA: own cases; unknown numbers: PI/FC);
- withdrawal deletes the files and rows;
- a reply that is the person's own invitation code is flagged "wants to answer by phone" and answered once; a random
  8-letter word is not; a code from a number on no record still finds its case; a KII code finds its KII record.
"""

import base64
import hashlib
import hmac
import os
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.services import issue_invitation
from apps.kii.services import create_kii_record, issue_kii_invitation
from apps.messaging import media, outreach, tasks
from apps.messaging import twilio_client as tw
from apps.messaging.models import InboundAttachment, InboundMessage, ReplyKind
from apps.sampling.services import transition_workflow_status

pytestmark = pytest.mark.django_db
MOBILE = "263771234567"
INBOUND = "/api/v1/twilio/inbound/"
VCARD = b"BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Tendai Moyo\r\nTEL;type=CELL:+263 77 123 4567\r\nEMAIL:tendai@kushinga.ac.zw\r\nEND:VCARD\r\n"


@pytest.fixture
def twilio(settings, monkeypatch, tmp_path):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    settings.PRIVATE_DATA_ROOT = str(tmp_path)
    settings.WHATSAPP_MEDIA_MAX_MB = 1
    sent, files = [], {}

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued"}))

    def get(url, auth=None, timeout=None, **kw):
        if url.endswith("/Media.json"):
            msid = url.split("/Messages/")[1].split("/")[0]
            return Mock(status_code=200, json=Mock(return_value={"media_list": [
                {"sid": f"ME{i}", "content_type": ct, "uri": f"/2010-04-01/Accounts/ACtest/Messages/{msid}/Media/ME{i}.json"}
                for i, (ct, _) in enumerate(files.get(msid, []))]}))
        msid, me = url.split("/Messages/")[1].split("/Media/")
        return Mock(status_code=200, content=files[msid][int(me[2:])][1])

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(media.requests, "get", get)
    monkeypatch.setattr(tasks.handle_inbound_message, "delay", lambda *args: outreach.handle_inbound(*args))
    post.files = files
    post.sent = sent
    return post


def _sign(url, params):
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(b"secret-token", payload.encode(), hashlib.sha1).digest()).decode()


_n = iter(range(1000, 9999))


def _send(body="", *, number=MOBILE, media=None, twilio=None):
    sid = f"SMin{next(_n)}"
    params = {"MessageSid": sid, "From": f"whatsapp:+{number}", "To": "whatsapp:+15550001111", "Body": body,
              "NumMedia": str(len(media or []))}
    if media:
        twilio.files[sid] = media
    resp = APIClient().post(INBOUND, urlencode(params), content_type="application/x-www-form-urlencoded",
                            HTTP_X_TWILIO_SIGNATURE=_sign(tw.inbound_url(), params))
    assert resp.status_code == 200
    return InboundMessage.objects.get(provider_sid=sid)


def _case_with_person(main_case, phone="0771234567"):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(main_case, status)
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD, is_eligible=True, phone=phone)
    return main_case


def _client(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    user = User.objects.create_user(username=username, password="x", role=role_obj)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


# --- Attachments ---------------------------------------------------------------------------------------------------

def test_a_voice_note_and_a_shared_contact_are_kept_and_the_contact_is_read(twilio, main_case):
    _case_with_person(main_case)
    message = _send("", media=[("audio/ogg", b"OggS-voice"), ("text/vcard", VCARD)], twilio=twilio)
    voice, contact = message.attachments.order_by("id")
    assert (voice.kind, contact.kind) == ("VOICE", "CONTACT") and message.has_attachments
    with open(media.file_path(voice), "rb") as fh:
        assert fh.read() == b"OggS-voice"
    assert contact.contact_text == "Tendai Moyo, +263 77 123 4567, tendai@kushinga.ac.zw"
    assert message.needs_person  # a person still reads it
    assert not os.path.relpath(media.file_path(voice), media.settings.PRIVATE_DATA_ROOT).startswith("..")


def test_a_file_over_the_size_cap_is_refused_and_the_message_is_kept(twilio, main_case):
    _case_with_person(main_case)
    message = _send("see attached", media=[("video/mp4", b"x" * (2 * 1024 * 1024))], twilio=twilio)
    [att] = message.attachments.all()
    assert att.file_ref == "" and "larger than" in att.error and message.body == "see attached"


def test_fetching_again_does_nothing(twilio, main_case):
    _case_with_person(main_case)
    message = _send("", media=[("image/jpeg", b"jpg")], twilio=twilio)
    assert media.fetch_attachments(message) == 0 and message.attachments.count() == 1


def test_an_attachment_opens_only_for_someone_who_may_see_the_conversation(twilio, main_case):
    _case_with_person(main_case)
    message = _send("", media=[("image/jpeg", b"JPEGDATA")], twilio=twilio)
    url = f"/api/v1/communications/attachments/{message.attachments.get().pk}/"
    fc, _ = _client(Role.FIELD_COORDINATOR, "m_fc")
    resp = fc.get(url)
    assert resp.status_code == 200 and b"".join(resp.streaming_content) == b"JPEGDATA" and resp["Content-Type"] == "image/jpeg"
    assert AuditEvent.objects.filter(action="communication.attachment_opened").exists()
    ra, ra_user = _client(Role.CONTACT_RA, "m_ra")
    assert ra.get(url).status_code == 404
    main_case.assigned_ra = ra_user
    main_case.save(update_fields=["assigned_ra"])
    assert ra.get(url).status_code == 200
    for role in (Role.ANALYST, Role.DOCUMENTARY_RA):
        assert _client(role, f"m_{role.lower()}")[0].get(url).status_code == 403
    assert APIClient().get(url).status_code == 401
    unknown = _send("", number="263712000999", media=[("image/png", b"PNG")], twilio=twilio)
    unknown_url = f"/api/v1/communications/attachments/{unknown.attachments.get().pk}/"
    assert fc.get(unknown_url).status_code == 200 and ra.get(unknown_url).status_code == 404


def test_the_thread_shows_the_attachments(twilio, main_case):
    from apps.messaging.communications import thread

    _case_with_person(main_case)
    _send("", media=[("text/vcard", VCARD)], twilio=twilio)
    _, fc = _client(Role.FIELD_COORDINATOR, "m_fc2")
    item = next(i for i in thread(fc, "main", main_case.pk)["items"] if i["type"] == "in")
    assert item["attachments"][0]["label"] == "Shared contact" and "Tendai Moyo" in item["attachments"][0]["contact"]


def test_withdrawal_deletes_the_files(twilio, main_case):
    from apps.consent.withdrawal import record_withdrawal

    _case_with_person(main_case)
    message = _send("", media=[("audio/ogg", b"voice")], twilio=twilio)
    path = media.file_path(message.attachments.get())
    _, fc = _client(Role.FIELD_COORDINATOR, "m_fc3")
    record_withdrawal(main_case, reason="Asked to withdraw", recorded_by=fc)
    assert not os.path.exists(path) and not InboundAttachment.objects.exists()


# --- Invitation codes ----------------------------------------------------------------------------------------------

def test_their_own_invitation_code_means_they_want_to_answer_by_phone(twilio, main_case):
    _case_with_person(main_case)
    _, code, _ = issue_invitation(main_case)
    message = _send(code.lower(), twilio=twilio)
    assert message.kind == ReplyKind.PHONE and message.needs_person
    assert "call you" in twilio.sent[-1]["Body"]
    assert AuditEvent.objects.filter(action="conversation.phone_requested").exists()
    replies = len(twilio.sent)
    _send(f"My code is {code}", twilio=twilio)  # inside a sentence too; answered once a day
    assert InboundMessage.objects.filter(kind=ReplyKind.PHONE).count() == 2 and len(twilio.sent) == replies


def test_a_random_word_of_the_same_length_is_not_a_code(twilio, main_case):
    _case_with_person(main_case)
    issue_invitation(main_case)
    assert _send("CALCLWRX", twilio=twilio).kind == ReplyKind.OTHER
    assert _send("Yes", twilio=twilio).kind == ReplyKind.YES


def test_a_code_from_a_number_on_no_record_finds_its_case(twilio, main_case):
    _case_with_person(main_case)
    _, code, _ = issue_invitation(main_case)
    message = _send(code, number="263712000555", twilio=twilio)
    assert message.kind == ReplyKind.PHONE and message.sample_case_id == main_case.pk


def test_a_kii_code_finds_its_kii_record(twilio):
    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Director", stakeholder_category="Bank",
                               status="PROSPECT", phone="0772000111", metadata={"organisation_name": "Agri Bank"})
    _, code, _ = issue_kii_invitation(record)
    message = _send(code, number="263772000111", twilio=twilio)
    assert message.kind == ReplyKind.PHONE and message.kii_record_id == record.pk
