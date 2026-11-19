"""The Research Assistant (calls) works key informants as well as Main-400 respondents, and anyone who phones a
participant can send them the study's information documents (PI, 19 Nov 2026). Under test:

- a Research Assistant (calls) opens the KII Register and the records assigned to it -- and only those: another
  RA's record 404s on the register, the record page, the link history, the "ask first" introduction and the
  never-answered list. It corrects its own record's contact details and sends that record a link, but never registers
  a record or changes status, consent, transcript or coding (the KII RA's interview work);
- its interview sheet reaches only the cases and KII records assigned to it;
- a document is marked "send to participants who ask" only when it contains no phrase participants must never see
  (AGENTS.md rule 2), checked again at every send; a replaced file that fails stops being sent;
- the documents go by email (attached) or WhatsApp from the study number (one PDF, only inside the 24-hour window),
  or are recorded as sent from the RA's own phone; never to a participant who withdrew, never for a case not theirs;
- the Supervisor sees what would be sent but sends nothing; the combined PDF is served only at the keyed address.
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from pypdf import PdfWriter
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.clearance import brief
from apps.clearance import services as clearance
from apps.clearance.models import ClearanceDocument
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.models import ContactEvent, ContactOutcome, Respondent
from apps.kii.services import create_kii_record
from apps.messaging import twilio_client as tw
from apps.messaging.hashing import number_hash
from apps.messaging.models import InboundMessage, MessagePurpose, Outreach, OutreachStatus, ProviderMessage

pytestmark = pytest.mark.django_db
MOBILE = "263772111222"


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def people(db):
    return {"rudo": _user(Role.TELEPHONE_RA, "rudo"), "tino": _user(Role.TELEPHONE_RA, "tino"),
            "kii_ra": _user(Role.KII_RA, "kiira"), "pi": _user(Role.PI_ADMIN, "pi"),
            "sup": _user(Role.SUPERVISOR_READONLY, "sup"), "contact": _user(Role.CONTACT_RA, "contactra")}


@pytest.fixture
def records(people):
    mine = create_kii_record(participant_name="Tendai Moyo", participant_role="Head", stakeholder_category="Bank",
                             metadata={"organisation_name": "CBZ Bank"}, phone="0772222222", assigned_ra=people["rudo"])
    other = create_kii_record(participant_name="Rudo Chari", participant_role="Head", stakeholder_category="Bank",
                              metadata={"organisation_name": "AFC"}, phone="0773333333", assigned_ra=people["tino"])
    return {"mine": mine, "other": other}


# --- The KII Register for the Research Assistant (calls) --------------------------------------------------------------

def test_a_calls_ra_lists_and_opens_only_its_own_kii_records(people, records):
    client = _client(people["rudo"])
    listed = client.get("/api/v1/kii/").json()
    assert [r["kii_id"] for r in listed["results"]] == [records["mine"].kii_id]
    assert client.get(f"/api/v1/kii/{records['mine'].pk}/").status_code == 200
    assert client.get(f"/api/v1/kii/{records['other'].pk}/").status_code == 404
    # The KII RA still sees every record.
    assert len(_client(people["kii_ra"]).get("/api/v1/kii/").json()["results"]) == 2


def test_a_calls_ra_corrects_its_own_records_contacts_but_not_anyone_elses(people, records):
    client = _client(people["rudo"])
    assert client.patch(f"/api/v1/kii/{records['mine'].pk}/", {"whatsapp_number": "0772999888"}, format="json").status_code == 200
    records["mine"].refresh_from_db()
    assert records["mine"].whatsapp_number == "0772999888"
    assert client.patch(f"/api/v1/kii/{records['other'].pk}/", {"phone": "0770000000"}, format="json").status_code == 404


def test_a_calls_ra_never_registers_a_record_or_does_the_kii_ras_interview_work(people, records):
    client = _client(people["rudo"])
    made = client.post("/api/v1/kii/", {"participant_name": "New", "participant_role": "x", "stakeholder_category": "Bank"},
                       format="json")
    assert made.status_code == 403
    pk = records["mine"].pk
    assert client.post(f"/api/v1/kii/{pk}/status/", {"status": "SCHEDULED"}, format="json").status_code == 403
    assert client.post(f"/api/v1/kii/{pk}/consent/", {"consent_type": "PARTICIPATION", "decision": "GIVEN"},
                       format="json").status_code == 403
    assert client.post(f"/api/v1/kii/{pk}/transcript-status/", {"transcript_status": "IN_PROGRESS"}, format="json").status_code == 403
    assert client.post(f"/api/v1/kii/{pk}/coding-status/", {"coding_status": "IN_PROGRESS"}, format="json").status_code == 403


def test_a_calls_ra_sends_its_own_record_a_link_and_no_one_elses(people, records):
    client = _client(people["rudo"])
    issued = client.post("/api/v1/kii-invitations/", {"kii_id": records["mine"].kii_id, "channel": "WHATSAPP"}, format="json")
    assert issued.status_code == 201
    assert client.get(f"/api/v1/kii-invitations/?kii_id={records['mine'].kii_id}").status_code == 200
    assert client.post("/api/v1/kii-invitations/", {"kii_id": records["other"].kii_id, "channel": "WHATSAPP"},
                       format="json").status_code == 404
    assert client.get(f"/api/v1/kii-invitations/?kii_id={records['other'].kii_id}").status_code == 404
    theirs = _client(people["tino"]).post("/api/v1/kii-invitations/", {"kii_id": records["other"].kii_id}, format="json").json()
    assert client.post(f"/api/v1/kii-invitations/{theirs['token_id']}/revoke/", {"reason": "x"}, format="json").status_code == 404
    assert client.get(f"/api/v1/kii-outreach/?kii_id={records['other'].kii_id}").status_code == 404


def test_the_never_answered_list_shows_a_calls_ra_only_its_own_informants(people, records):
    for record in records.values():
        record.status = "PROSPECT"  # still waiting: asked first, never invited
        record.save(update_fields=["status"])
        Outreach.objects.create(kii_record=record, status=OutreachStatus.NO_REPLY, channel="WHATSAPP", number_hash="h",
                                number_masked="+263 ••• 222", intro_sent_at="2026-11-01T08:00:00Z")
    rows = _client(people["rudo"]).get("/api/v1/kii-outreach/unanswered/").json()["results"]
    assert [r["kii_id"] for r in rows] == [records["mine"].kii_id]
    assert _client(people["kii_ra"]).get("/api/v1/kii-outreach/unanswered/").json()["count"] == 2


def test_the_interview_sheet_reaches_only_a_calls_ras_own_case_or_record(people, records, main_case):
    from apps.proit.views import _scoped_profile_or_404

    main_case.assigned_ra = people["rudo"]
    request = SimpleNamespace(user=people["rudo"])
    mine = SimpleNamespace(sample_case_id=None, sample_case=None, kii_record_id=records["mine"].pk, kii_record=records["mine"])
    theirs = SimpleNamespace(sample_case_id=None, sample_case=None, kii_record_id=records["other"].pk, kii_record=records["other"])
    case = SimpleNamespace(sample_case_id=main_case.pk, sample_case=main_case, kii_record_id=None, kii_record=None)
    assert _scoped_profile_or_404(request, mine) is mine
    assert _scoped_profile_or_404(request, case) is case
    with pytest.raises(Http404):
        _scoped_profile_or_404(request, theirs)


# --- The study information documents ---------------------------------------------------------------------------------

def _text_pdf(text: str) -> bytes:
    """A one-page PDF whose text layer holds `text` (pypdf writes no text, so the page stream is built by hand)."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for n, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def docs(settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = str(tmp_path)
    settings.STUDY_LETTERS_KEY = "s3cret-key"
    brief._text_cache.clear()
    brief._pack_cache.clear()
    made = {}
    for title, content in (("ABF-FST Study Brief", _text_pdf("Why the study is being conducted")),
                           ("Old brief", _text_pdf("Participation does not promise loan approval")),
                           ("Concept note", _blank_pdf())):
        doc = ClearanceDocument.objects.create(title=title, issuing_body="CUT", document_type="OTHER")
        clearance.save_file(doc, SimpleUploadedFile(title.replace(" ", "_") + ".pdf", content, content_type="application/pdf"),
                            user=None)
        made[title] = doc
    return made


def test_a_document_is_marked_for_sending_only_without_a_forbidden_phrase(people, docs):
    pi = _client(people["pi"])
    refused = pi.patch(f"/api/v1/clearance-documents/{docs['Old brief'].pk}/", {"in_study_brief": True}, format="json")
    assert refused.status_code == 409 and "loan approval" in refused.json()["error"]["message"]
    docs["Old brief"].refresh_from_db()
    assert docs["Old brief"].in_study_brief is False
    ok = pi.patch(f"/api/v1/clearance-documents/{docs['ABF-FST Study Brief'].pk}/", {"in_study_brief": True}, format="json")
    assert ok.status_code == 200 and ok.json()["in_study_brief"] is True
    assert AuditEvent.objects.filter(action="clearance.study_brief_changed").count() == 1


def test_switching_a_letter_off_is_audited(people, docs):
    _client(people["pi"]).patch(f"/api/v1/clearance-documents/{docs['Concept note'].pk}/", {"active": False}, format="json")
    assert AuditEvent.objects.filter(action="clearance.active_changed", object_id=str(docs["Concept note"].pk)).exists()


def test_a_replaced_file_with_a_forbidden_phrase_stops_being_sent(people, docs):
    doc = docs["ABF-FST Study Brief"]
    doc.in_study_brief = True
    doc.save()
    upload = SimpleUploadedFile("new.pdf", _text_pdf("a guarantee of finance"), content_type="application/pdf")
    resp = _client(people["pi"]).post(f"/api/v1/clearance-documents/{doc.pk}/file/", {"file": upload}, format="multipart")
    assert resp.status_code == 200 and resp.json()["in_study_brief"] is False


@pytest.fixture
def marked(docs):
    for title in ("ABF-FST Study Brief", "Concept note"):
        docs[title].in_study_brief = True
        docs[title].save()
    return docs


@pytest.fixture
def jane(main_case, people):
    main_case.assigned_ra = people["rudo"]
    main_case.save(update_fields=["assigned_ra"])
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", email="jane@farmco.co.zw",
                              phone="+" + MOBILE, whatsapp_number="+" + MOBILE)
    return main_case


def test_the_documents_go_by_email_attached_and_on_the_timeline(people, marked, jane):
    resp = _client(people["rudo"]).post("/api/v1/study-brief/", {"kind": "main", "id": jane.sample_id, "channel": "EMAIL"},
                                        format="json")
    assert resp.status_code == 201, resp.json()
    sent = mail.outbox[0]
    assert sorted(n for n, _, _ in sent.attachments) == ["ABF-FST_Study_Brief.pdf", "Concept_note.pdf"]
    assert sent.body.startswith("Hello Jane Doe,") and "s3cret-key" not in sent.body  # files attached, no link
    message = ProviderMessage.objects.get()
    assert message.purpose == MessagePurpose.STUDY_INFO and message.sent_by == people["rudo"]
    assert AuditEvent.objects.filter(action="study_brief.sent").count() == 1


def test_nothing_is_sent_while_a_marked_document_holds_a_forbidden_phrase(people, marked, jane):
    ClearanceDocument.objects.filter(pk=marked["Concept note"].pk).update(description="Not a credit rating")
    resp = _client(people["rudo"]).post("/api/v1/study-brief/", {"kind": "main", "id": jane.sample_id, "channel": "EMAIL"},
                                        format="json")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "blocked_phrase"
    assert not mail.outbox and not ProviderMessage.objects.exists()


def test_never_for_a_case_that_is_not_theirs_or_a_participant_who_withdrew(people, marked, jane):
    assert _client(people["tino"]).post("/api/v1/study-brief/", {"kind": "main", "id": jane.sample_id, "channel": "EMAIL"},
                                        format="json").status_code == 404
    record_consent(sample_case=jane, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.WITHDRAWN,
                   information_sheet_version="", method=ConsentMethod.VERBAL_RA_RECORDED)
    resp = _client(people["rudo"]).post("/api/v1/study-brief/", {"kind": "main", "id": jane.sample_id, "channel": "EMAIL"},
                                        format="json")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "withdrawn"
    assert not mail.outbox


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued"}))

    monkeypatch.setattr(tw.requests, "post", post)
    return sent


def test_whatsapp_from_the_study_number_only_inside_the_24_hour_window(people, marked, jane, twilio):
    client = _client(people["rudo"])
    body = {"kind": "main", "id": jane.sample_id, "channel": "WHATSAPP"}
    closed = client.post("/api/v1/study-brief/", body, format="json")
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "window_closed" and not twilio
    InboundMessage.objects.create(provider_sid="SMin1", sample_case=jane, number_hash=number_hash(MOBILE), from_masked="x",
                                  body="Please send me the documents")
    assert client.post("/api/v1/study-brief/", body, format="json").status_code == 201
    assert twilio[0]["MediaUrl"].endswith("/s3cret-key/ABF-FST-Study-Information.pdf")


def test_sent_from_the_ras_own_phone_is_recorded_on_the_timeline(people, marked, jane):
    client = _client(people["rudo"])
    info = client.get(f"/api/v1/study-brief/?kind=main&id={jane.sample_id}").json()
    assert info["by_hand_link"].startswith(f"https://wa.me/{MOBILE}?text=") and "s3cret-key" in info["message"]
    assert client.post("/api/v1/study-brief/sent-by-hand/", {"kind": "main", "id": jane.sample_id}, format="json").status_code == 201
    event = ContactEvent.objects.get()
    assert event.outcome == ContactOutcome.STUDY_INFO_SENT and event.ra == people["rudo"]


def test_a_kii_record_can_be_sent_the_documents_too(people, marked, records):
    records["mine"].email = "tendai@cbz.co.zw"
    records["mine"].save()
    resp = _client(people["rudo"]).post("/api/v1/study-brief/", {"kind": "kii", "id": records["mine"].kii_id, "channel": "EMAIL"},
                                        format="json")
    assert resp.status_code == 201 and len(mail.outbox[0].attachments) == 2


def test_the_supervisor_sees_what_would_be_sent_but_sends_nothing(people, marked, jane):
    client = _client(people["sup"])
    assert client.get(f"/api/v1/study-brief/?kind=main&id={jane.sample_id}").status_code == 200
    assert client.post("/api/v1/study-brief/", {"kind": "main", "id": jane.sample_id, "channel": "EMAIL"},
                       format="json").status_code == 403


def test_the_combined_pdf_is_served_only_at_the_keyed_address(marked, settings):
    anon = APIClient()
    assert anon.get("/api/v1/study-letters/wrong-key/ABF-FST-Study-Information.pdf").status_code == 404
    resp = anon.get("/api/v1/study-letters/s3cret-key/ABF-FST-Study-Information.pdf")
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"


# --- The PI's send-as-it-is decision (19 Nov 2026) --------------------------------------------------------------------

def test_the_pi_can_record_that_a_document_goes_as_it_is_with_a_reason(people, docs, main_case):
    pi = _client(people["pi"])
    url = f"/api/v1/clearance-documents/{docs['Old brief'].pk}/"
    assert pi.patch(url, {"wording_exception": True, "wording_exception_reason": ""}, format="json").status_code == 400
    granted = pi.patch(url, {"wording_exception": True,
                             "wording_exception_reason": "Reviewed and agreed to go to respondents unchanged"}, format="json")
    assert granted.status_code == 200 and granted.json()["has_wording_exception"] is True
    assert granted.json()["forbidden_phrase"] == "loan approval"  # still shown: the decision does not hide the word
    assert pi.patch(url, {"in_study_brief": True}, format="json").status_code == 200
    event = AuditEvent.objects.get(action="clearance.wording_exception_granted")
    assert event.metadata["phrase"] == "loan approval" and event.user == people["pi"]
    # ...and it is then sent.
    main_case.assigned_ra = people["rudo"]
    main_case.save(update_fields=["assigned_ra"])
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", email="jane@farmco.co.zw")
    sent = _client(people["rudo"]).post("/api/v1/study-brief/", {"kind": "main", "id": main_case.sample_id, "channel": "EMAIL"},
                                        format="json")
    assert sent.status_code == 201 and [n for n, _, _ in mail.outbox[0].attachments] == ["Old_brief.pdf"]


def test_only_the_pi_records_it(people, docs):
    for who in ("rudo", "sup"):
        resp = _client(people[who]).patch(f"/api/v1/clearance-documents/{docs['Old brief'].pk}/",
                                          {"wording_exception": True, "wording_exception_reason": "I think it is fine"},
                                          format="json")
        assert resp.status_code == 403
    docs["Old brief"].refresh_from_db()
    assert not docs["Old brief"].has_wording_exception


def test_a_replaced_file_loses_the_decision_and_is_checked_again(people, docs):
    pi = _client(people["pi"])
    url = f"/api/v1/clearance-documents/{docs['Old brief'].pk}/"
    pi.patch(url, {"wording_exception": True, "wording_exception_reason": "Reviewed and agreed as it is"}, format="json")
    pi.patch(url, {"in_study_brief": True}, format="json")
    upload = SimpleUploadedFile("v2.pdf", _text_pdf("now with a guarantee"), content_type="application/pdf")
    replaced = pi.post(f"{url}file/", {"file": upload}, format="multipart").json()
    assert replaced["has_wording_exception"] is False and replaced["in_study_brief"] is False


def test_withdrawing_the_decision_stops_the_document_being_sent(people, docs):
    pi = _client(people["pi"])
    url = f"/api/v1/clearance-documents/{docs['Old brief'].pk}/"
    pi.patch(url, {"wording_exception": True, "wording_exception_reason": "Reviewed and agreed as it is"}, format="json")
    pi.patch(url, {"in_study_brief": True}, format="json")
    withdrawn = pi.patch(url, {"wording_exception": False}, format="json").json()
    assert withdrawn["has_wording_exception"] is False and withdrawn["in_study_brief"] is False
    assert AuditEvent.objects.filter(action="clearance.wording_exception_withdrawn").exists()


# --- The PDF on a Meta-approved template outside the 24-hour window (19 Nov 2026) -------------------------------------

def test_outside_the_window_the_pdf_goes_on_the_approved_template(people, marked, jane, twilio, settings, monkeypatch):
    settings.TWILIO_WA_CONTENT_STUDY_INFO = "HXstudyinfo"
    body = {"kind": "main", "id": jane.sample_id, "channel": "WHATSAPP"}
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [{"sid": "HXstudyinfo", "status": "pending"}])
    waiting = _client(people["rudo"]).post("/api/v1/study-brief/", body, format="json")
    assert waiting.status_code == 409 and waiting.json()["error"]["code"] == "window_closed" and not twilio
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [{"sid": "HXstudyinfo", "status": "approved"}])
    assert _client(people["rudo"]).get(f"/api/v1/study-brief/?kind=main&id={jane.sample_id}").json()["whatsapp_template_ready"]
    sent = _client(people["rudo"]).post("/api/v1/study-brief/", body, format="json")
    assert sent.status_code == 201, sent.json()
    assert twilio[0]["ContentSid"] == "HXstudyinfo" and "Jane Doe" in twilio[0]["ContentVariables"]
    message = ProviderMessage.objects.get()
    assert message.is_template and message.purpose == MessagePurpose.STUDY_INFO
