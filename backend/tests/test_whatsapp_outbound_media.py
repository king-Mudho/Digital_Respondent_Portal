"""Sending on WhatsApp from Communications beyond text (2026-11-04): documents, pictures, videos, voice notes recorded
in the browser, and contacts; logging WhatsApp voice and video calls; narrowing the list by what happened; the fuller
contact card. Twilio is a fake requests.post. Under test:

- a file goes only where a written WhatsApp may: a number on the record, inside 24 hours of their own last message,
  not to a locked Reserve or a read-only role, and never with a word respondents must not see (AGENTS.md rules 2, 4);
- a file is checked by its first bytes and size before anything is sent; HEIC/MOV get an answer saying what to do;
- Twilio fetches the file through a signed link that names one file, refuses tampering, and expires;
- a Chrome recording (WebM/Opus) becomes an Ogg/Opus voice note with valid pages, sound untouched;
- files the study sent are opened only by people who may see the conversation, and deleted on withdrawal;
- the list narrows to read / delivered-not-read / replied / never replied / called / not called, with counts.
"""

import os
import struct
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import ContactChannel, ContactEvent, ContactOutcome, Respondent, RoleCategory
from apps.kii.services import create_kii_record
from apps.messaging import communications as comms
from apps.messaging import media_out, outreach, voice
from apps.messaging import twilio_client as tw
from apps.messaging.models import (
    InboundMessage,
    MessageChannel,
    MessagePurpose,
    OutboundAttachment,
    ProviderMessage,
    ProviderStatus,
)

THREADS = "/api/v1/communications/threads/"
NUMBER = "263771234567"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"x" * 64


@pytest.fixture
def twilio(settings, monkeypatch, tmp_path):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    settings.PRIVATE_DATA_ROOT = str(tmp_path)
    settings.APP_DOMAIN = "research.agribizframework.com"
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SMm{len(sent):04d}", "status": "queued"}))

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [])
    return sent


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _client(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.fixture
def pi(db):
    return _user(Role.PI_ADMIN, "media_pi")


@pytest.fixture
def person(main_case):
    return Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
                                     is_eligible=True, phone="0771234567", whatsapp_number="077 123 4567")


def _wrote_in(case, minutes_ago=5):
    """They wrote to the study on WhatsApp, which opens WhatsApp's 24 hours."""
    message = InboundMessage.objects.create(
        channel=MessageChannel.WHATSAPP, provider_sid=f"SMin-{InboundMessage.objects.count()}", sample_case=case,
        number_hash=outreach.number_hash(NUMBER), from_masked=tw.mask(NUMBER), body="Hello", needs_person=True)
    InboundMessage.objects.filter(pk=message.pk).update(received_at=timezone.now() - timedelta(minutes=minutes_ago))
    return message


def _send_files(user, case, files, **data):
    from django.core.files.uploadedfile import SimpleUploadedFile

    uploads = [SimpleUploadedFile(name, content) for name, content in files]
    return _client(user).post(f"{THREADS}main/{case.pk}/media/", {"recipient": NUMBER, "files": uploads, **data},
                              format="multipart")


# --- Sending a file ------------------------------------------------------------------------------------------------

def test_a_picture_goes_through_a_signed_link_twilio_can_fetch(twilio, pi, person, main_case):
    _wrote_in(main_case)
    resp = _send_files(pi, main_case, [("Farm visit.png", PNG)], caption="The photo we discussed")
    assert resp.status_code == 201, resp.content
    data = twilio[-1]
    assert data["To"] == f"whatsapp:+{NUMBER}" and data["Body"] == "The photo we discussed"
    assert data["MediaUrl"].startswith("https://research.agribizframework.com/api/v1/twilio/media/")
    assert data["MediaUrl"].endswith("/Farm visit.png")
    message = ProviderMessage.objects.get(provider_sid="SMm0001")
    assert message.body == "[Picture: Farm visit.png]\nThe photo we discussed" and not message.is_template
    attachment = OutboundAttachment.objects.get(message=message)
    assert open(os.path.join(media_out.settings.PRIVATE_DATA_ROOT, attachment.file_ref), "rb").read() == PNG

    # Twilio fetches it without signing in: the link is the credential.
    path = data["MediaUrl"].split("research.agribizframework.com", 1)[1]
    fetched = _client().get(path)
    assert fetched.status_code == 200 and b"".join(fetched.streaming_content) == PNG
    assert fetched["Content-Type"] == "image/png"
    # The waiting message counts as answered.
    assert not InboundMessage.objects.filter(sample_case=main_case, handled_at=None).exists()


def test_the_signed_link_refuses_tampering_and_expires(twilio, pi, person, main_case, settings):
    _wrote_in(main_case)
    _send_files(pi, main_case, [("a.pdf", PDF)])
    token = twilio[-1]["MediaUrl"].split("/twilio/media/", 1)[1].split("/", 1)[0]
    assert _client().get(f"/api/v1/twilio/media/{token[:-2]}xx/a.pdf").status_code == 404
    forged = media_out.signing.dumps({"f": "../secret.txt", "t": "text/plain"}, salt=media_out.SALT, compress=False)
    assert _client().get(f"/api/v1/twilio/media/{forged}/x.txt").status_code == 404  # never outside the folder
    settings.WHATSAPP_MEDIA_LINK_MINUTES = -1
    assert _client().get(f"/api/v1/twilio/media/{token}/a.pdf").status_code == 404


def test_no_file_goes_outside_whatsapps_24_hours(twilio, pi, person, main_case):
    resp = _send_files(pi, main_case, [("a.pdf", PDF)])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "window_closed"
    _wrote_in(main_case, minutes_ago=25 * 60)  # their last message is too old
    resp = _send_files(pi, main_case, [("a.pdf", PDF)])
    assert resp.status_code == 409 and twilio == [] and not OutboundAttachment.objects.exists()


def test_a_file_is_refused_for_a_locked_reserve_a_read_only_role_and_forbidden_words(twilio, pi, person, main_case,
                                                                                     locked_reserve_case):
    _wrote_in(main_case)
    Respondent.objects.create(sample_case=locked_reserve_case, full_name="R", whatsapp_number="0771234567")
    _wrote_in(locked_reserve_case)
    resp = _send_files(pi, locked_reserve_case, [("a.pdf", PDF)])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "not_contactable"
    supervisor = _user(Role.SUPERVISOR_READONLY, "media_sup")
    assert _send_files(supervisor, main_case, [("a.pdf", PDF)]).status_code == 403
    resp = _send_files(pi, main_case, [("a.pdf", PDF)], caption="Your loan approval letter")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "blocked_phrase"
    resp = _send_files(pi, main_case, [("Credit rating.pdf", PDF)])
    assert resp.json()["error"]["code"] == "blocked_phrase"
    resp = _client(pi).post(f"{THREADS}main/{main_case.pk}/media/", {"recipient": "263779999999"}, format="multipart")
    assert resp.status_code == 400
    assert twilio == []


def test_a_file_is_checked_by_what_it_is_not_only_its_name(twilio, pi, person, main_case, settings):
    _wrote_in(main_case)
    resp = _send_files(pi, main_case, [("photo.png", b"GIF89a not a png at all")])
    assert resp.status_code == 400 and "not really a PNG" in resp.json()["error"]["message"]
    resp = _send_files(pi, main_case, [("IMG_0001.HEIC", b"....ftypheic")])
    assert "Save it as JPG" in resp.json()["error"]["message"]
    resp = _send_files(pi, main_case, [("clip.mov", b"....ftypqt  ")])
    assert "MP4" in resp.json()["error"]["message"]
    settings.WHATSAPP_IMAGE_MAX_MB = 0.00001
    resp = _send_files(pi, main_case, [("big.png", PNG)])
    assert "up to" in resp.json()["error"]["message"]
    # One bad file stops the whole send before anything goes.
    resp = _send_files(pi, main_case, [("good.pdf", PDF), ("bad.png", b"nope")])
    assert resp.status_code == 400 and twilio == [] and not ProviderMessage.objects.exists()


def test_several_files_go_one_message_each_with_the_caption_on_the_first(twilio, pi, person, main_case):
    _wrote_in(main_case)
    resp = _send_files(pi, main_case, [("Info sheet.pdf", PDF), ("map.png", PNG)], caption="As promised")
    assert resp.status_code == 201
    assert [d.get("Body") for d in twilio] == ["As promised", None]
    assert [a.kind for a in OutboundAttachment.objects.order_by("id")] == ["DOCUMENT", "IMAGE"]


# --- Voice notes ---------------------------------------------------------------------------------------------------

def _ebml(element: bytes, body: bytes, unknown_size: bool = False) -> bytes:
    size = b"\x01\xff\xff\xff\xff\xff\xff\xff" if unknown_size else b"\x01" + len(body).to_bytes(7, "big")
    return element + size + body


def chrome_recording(packets: list[bytes]) -> bytes:
    """A WebM file shaped like Chrome's MediaRecorder output: unknown-size Segment and Cluster, SimpleBlocks."""
    head = voice.opus_head(1)
    track = _ebml(b"\xae", _ebml(b"\xd7", b"\x01") + _ebml(b"\x86", b"A_OPUS") + _ebml(b"\x63\xa2", head)
                  + _ebml(b"\xe1", _ebml(b"\x9f", b"\x01")))
    blocks = b"".join(_ebml(b"\xa3", b"\x81" + struct.pack(">h", n * 20) + b"\x80" + p) for n, p in enumerate(packets))
    cluster = _ebml(b"\x1f\x43\xb6\x75", _ebml(b"\xe7", b"\x00") + blocks, unknown_size=True)
    segment = _ebml(b"\x18\x53\x80\x67", _ebml(b"\x16\x54\xae\x6b", track) + cluster, unknown_size=True)
    return _ebml(b"\x1a\x45\xdf\xa3", _ebml(b"\x42\x82", b"webm")) + segment


def _pages(ogg: bytes):
    pos, pages = 0, []
    while pos < len(ogg):
        assert ogg[pos:pos + 4] == b"OggS"
        _, _, flags, granule, _, seq, crc, count = struct.unpack("<4sBBqIIIB", ogg[pos:pos + 27])
        lacing = ogg[pos + 27: pos + 27 + count]
        end = pos + 27 + count + sum(lacing)
        page = bytearray(ogg[pos:end])
        page[22:26] = b"\x00\x00\x00\x00"
        assert voice._crc32_ogg(bytes(page)) == crc
        pages.append((flags, granule, seq, ogg[pos + 27 + count: end]))
        pos = end
    return pages


def test_a_chrome_recording_becomes_an_ogg_voice_note_with_the_sound_untouched():
    packets = [bytes([(19 << 3) | 0]) + bytes([n]) * 40 for n in range(5)]  # CELT, 20 ms, one frame each
    pages = _pages(voice.webm_to_ogg(chrome_recording(packets)))
    assert pages[0][3].startswith(b"OpusHead") and pages[0][0] == 0x02  # beginning of stream
    assert pages[1][3].startswith(b"OpusTags")
    assert [p[3] for p in pages[2:]] == packets
    assert [p[1] for p in pages[2:]] == [960 * (n + 1) for n in range(5)]  # 48 kHz samples so far
    assert pages[-1][0] == 0x04 and [p[2] for p in pages] == list(range(7))


def test_a_recorded_voice_note_is_sent_as_ogg_and_a_caption_follows_as_text(twilio, pi, person, main_case):
    _wrote_in(main_case)
    recording = chrome_recording([bytes([(19 << 3)]) + b"\x01" * 30] * 3)
    resp = _send_files(pi, main_case, [("blob", recording)], recording_type="audio/webm;codecs=opus",
                       caption="Here is my voice note")
    assert resp.status_code == 201, resp.content
    assert twilio[0]["MediaUrl"].endswith(".ogg") and "Body" not in twilio[0]
    assert twilio[1]["Body"] == "Here is my voice note" and "MediaUrl" not in twilio[1]
    attachment = OutboundAttachment.objects.get()
    assert (attachment.kind, attachment.content_type) == ("VOICE", "audio/ogg")
    assert open(os.path.join(media_out.settings.PRIVATE_DATA_ROOT, attachment.file_ref), "rb").read(4) == b"OggS"


# --- Opening and erasing what was sent -----------------------------------------------------------------------------

def test_a_sent_file_opens_only_for_people_who_may_see_the_conversation(twilio, pi, person, main_case):
    _wrote_in(main_case)
    _send_files(pi, main_case, [("a.pdf", PDF)])
    attachment = OutboundAttachment.objects.get()
    assert _client(pi).get(f"/api/v1/communications/sent-attachments/{attachment.pk}/").status_code == 200
    other_ra = _user(Role.CONTACT_RA, "media_ra")  # the case is not assigned to them
    assert _client(other_ra).get(f"/api/v1/communications/sent-attachments/{attachment.pk}/").status_code == 404
    thread = _client(pi).get(f"{THREADS}main/{main_case.pk}/").json()
    out = next(i for i in thread["items"] if i["type"] == "out")
    assert out["attachments"][0]["url"] == f"/communications/sent-attachments/{attachment.pk}/"


def test_withdrawal_deletes_the_files_the_study_sent(twilio, pi, person, main_case):
    from apps.consent.withdrawal import record_withdrawal

    _wrote_in(main_case)
    _send_files(pi, main_case, [("a.pdf", PDF)])
    path = os.path.join(media_out.settings.PRIVATE_DATA_ROOT, OutboundAttachment.objects.get().file_ref)
    record_withdrawal(main_case, reason="Asked to withdraw", recorded_by=pi)
    assert not OutboundAttachment.objects.exists() and not os.path.exists(path)


# --- Contacts and calls ----------------------------------------------------------------------------------------------

def test_a_contact_goes_as_a_card_and_only_inside_the_24_hours(twilio, pi, person, main_case):
    url = f"{THREADS}main/{main_case.pk}/contact/"
    body = {"recipient": NUMBER, "name": "Happyson Saina", "number": "+263 77 000 0000", "note": "Researcher"}
    assert _client(pi).post(url, body, format="json").status_code == 409
    _wrote_in(main_case)
    resp = _client(pi).post(url, body, format="json")
    assert resp.status_code == 201
    assert twilio[-1]["Body"] == "Contact: Happyson Saina\n+263 77 000 0000\nResearcher"
    assert _client(pi).post(url, {**body, "number": "12"}, format="json").json()["error"]["code"] == "no_number"


def test_a_whatsapp_video_call_is_logged_and_counts_as_called(pi, person, main_case):
    url = f"/api/v1/calls/main/{main_case.sample_id}/"
    resp = _client(pi).post(url, {"outcome": "REACHED", "channel": "WHATSAPP_VIDEO", "notes": "Booked Friday"}, format="json")
    assert resp.status_code == 201
    assert ContactEvent.objects.get().channel == ContactChannel.WHATSAPP_VIDEO
    assert _client(pi).post(url, {"outcome": "REACHED", "channel": "EMAIL"}, format="json").status_code == 400
    thread = _client(pi).get(f"{THREADS}main/{main_case.pk}/").json()
    assert any(i["type"] == "event" and i["text"] == "WhatsApp video call: Reached" for i in thread["items"])
    assert thread["calls"]["numbers"][0]["whatsapp_link"] == f"https://wa.me/{NUMBER}"
    assert thread["calls"]["numbers"][0]["tel"] == f"tel:+{NUMBER}"
    assert len(thread["calls"]["numbers"]) == 1  # phone and WhatsApp hold the same number


def test_a_kii_call_shows_in_its_conversation(pi):
    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Head", stakeholder_category="Bank",
                               metadata={"organisation_name": "CBZ Bank"}, phone="0772222222")
    ContactEvent.objects.create(kii_record=record, channel=ContactChannel.WHATSAPP_CALL, occurred_at=timezone.now(),
                                outcome=ContactOutcome.NO_ANSWER, ra=pi)
    thread = _client(pi).get(f"{THREADS}kii/{record.pk}/").json()
    assert any(i["type"] == "event" and i["text"] == "WhatsApp voice call: No answer" for i in thread["items"])
    assert thread["subject"]["progress"][-1]["value"] == "1 logged"


# --- Narrowing the list ----------------------------------------------------------------------------------------------

def _case_with(organisation_name, main_case_factory, status=None, replied=False, called=False, user=None):
    case = main_case_factory(organisation_name)
    if status:
        ProviderMessage.objects.create(sample_case=case, channel=MessageChannel.WHATSAPP, purpose=MessagePurpose.MESSAGE,
                                       to_masked="+263 •••", status=status, body="Hello")
    if replied:
        InboundMessage.objects.create(channel=MessageChannel.WHATSAPP, provider_sid=f"SMr-{case.pk}", sample_case=case,
                                      number_hash="h", from_masked="+263 •••", body="Thanks")
    if called:
        ContactEvent.objects.create(sample_case=case, channel=ContactChannel.PHONE, occurred_at=timezone.now(),
                                    outcome=ContactOutcome.NO_ANSWER, ra=user)
    return case


@pytest.fixture
def make_case(db, stratum):
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_organisation, create_sample_case

    def make(name):
        org = create_organisation(province="HARARE", name=name, district="Harare", actor_family="PRODUCER_PRIMARY",
                                  size_class="SME")
        return create_sample_case(organisation=org, stratum=stratum, sample_type=SampleType.MAIN, year=2026)

    return make


def test_the_list_narrows_by_read_delivered_replied_and_called_with_counts(pi, make_case):
    read = _case_with("Read Farm", make_case, status=ProviderStatus.READ, replied=True)
    unread = _case_with("Unread Farm", make_case, status=ProviderStatus.DELIVERED, called=True, user=pi)
    _case_with("Quiet Farm", make_case, status=ProviderStatus.SENT)

    def names(status):
        body = _client(pi).get(THREADS, {"status": status}).json()
        return sorted(r["organisation"] for r in body["results"]), {f["key"]: f["count"] for f in body["status_filters"]}

    got, counts = names("read")
    assert got == ["Read Farm"]
    assert counts == {"read": 1, "unread": 1, "no_report": 1, "replied": 1, "no_reply": 2, "called": 1, "not_called": 2}
    assert names("unread")[0] == ["Unread Farm"]
    assert names("no_report")[0] == ["Quiet Farm"]
    assert names("replied")[0] == ["Read Farm"]
    assert names("no_reply")[0] == ["Quiet Farm", "Unread Farm"]
    assert names("called")[0] == ["Unread Farm"]
    assert names("not_called")[0] == ["Quiet Farm", "Read Farm"]
    row = next(r for r in _client(pi).get(THREADS).json()["results"] if r["organisation"] == "Unread Farm")
    assert (row["called"], row["replied"], row["last_sent_status"]) == (True, False, "DELIVERED")
    assert read.pk != unread.pk


def test_the_contact_card_shows_every_number_with_links_and_where_they_stand(pi, person, main_case):
    person.gatekeeper_name, person.gatekeeper_contact = "Mary (PA)", "0242 700 000; 0773 333 333"
    person.save()
    card = comms.contact_card(main_case, "main")
    numbers = [n["number"] for n in card["people"][0]["numbers"]]
    assert numbers == ["077 123 4567", "0242 700 000", "0773 333 333"]  # 0771234567 is the same number
    assert card["people"][0]["gatekeeper"] == "Mary (PA) 0242 700 000; 0773 333 333"
    assert {"label": "District", "value": "Harare"} in card["details"]
    assert any(row["label"] == "Calls" and row["value"] == "None logged" for row in card["progress"])
