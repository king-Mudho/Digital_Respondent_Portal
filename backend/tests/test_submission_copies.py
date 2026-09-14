"""PDF copies of completed Kobo forms, and emailing them (added 2026-09-14)."""

import io
from unittest.mock import patch

import pytest
from django.core import mail
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.models import Respondent
from apps.kobo.pdf import render_submission_pdf

CONTENT = {
    "survey": [
        {"type": "start", "name": "start", "$xpath": "start"},
        {"type": "hidden", "name": "sample_id", "$xpath": "sample_id"},
        {"type": "begin_group", "name": "profile", "label": [None, "SECTION 2 — Profile"], "$xpath": "profile"},
        {"type": "select_one", "select_from_list_name": "org_type", "name": "P1",
         "label": [None, "Organisation type"], "$xpath": "profile/P1"},
        {"type": "select_multiple", "select_from_list_name": "factors", "name": "D2",
         "label": [None, "Which factors matter?"], "$xpath": "profile/D2"},
        {"type": "text", "name": "P1_OTHER", "label": [None, "If Other, please specify"], "$xpath": "profile/P1_OTHER"},
        {"type": "note", "name": "n1", "label": [None, "A note never printed"], "$xpath": "profile/n1"},
        {"type": "end_group", "name": "profile"},
        {"type": "begin_repeat", "name": "metric_repeat", "label": [None, "Metric"], "$xpath": "metric_repeat"},
        {"type": "text", "name": "value", "label": [None, "Value"], "$xpath": "metric_repeat/value"},
        {"type": "end_repeat", "name": "metric_repeat"},
    ],
    "choices": [
        {"list_name": "org_type", "name": "processor", "label": [None, "Processor"]},
        {"list_name": "factors", "name": "cashflow", "label": [None, "Cash-flow predictability"]},
        {"list_name": "factors", "name": "digital_records", "label": [None, "Digital records"]},
    ],
}


def _payload(sample_id="SID-2026-000418"):
    return {
        "_id": 77, "_submission_time": "2026-09-14T14:03:21", "sample_id": sample_id, "SAMPLE_ID_FINAL": sample_id,
        "profile/P1": "processor", "profile/D2": "cashflow digital_records",
        "metric_repeat": [{"metric_repeat/value": "120 tonnes"}, {"metric_repeat/value": "USD 40,000"}],
    }


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def test_the_pdf_prints_labels_not_codes_and_skips_what_was_not_asked():
    text = _text(render_submission_pdf(form_content=CONTENT, payload=_payload(), form_title="Main Study Questionnaire",
                                       record_label="SID-2026-000418"))
    assert "SID-2026-000418" in text
    assert "Organisation type" in text and "Processor" in text
    assert "Cash-flow predictability; Digital records" in text
    assert "Metric 1" in text and "120 tonnes" in text and "Metric 2" in text and "USD 40,000" in text
    assert "If Other, please specify" not in text  # unanswered
    assert "A note never printed" not in text
    assert "processor" not in text  # the code itself


# --- API -----------------------------------------------------------------------

@pytest.fixture
def kobo(settings):
    settings.KOBO_API_TOKEN = "token"
    settings.KOBO_ASSET_UID = "q-asset"
    settings.KOBO_KII_ASSET_UID = "kii-asset"
    settings.KOBO_DOCUMENTS_ASSET_UID = ""

    def fake_get(path, **params):
        if path.endswith("/data/77/"):
            return _payload()
        if "/data/" in path:
            return {"count": 1, "results": [_payload()]}
        return {"content": CONTENT}

    with patch("apps.kobo.submission_copies._kobo_get", side_effect=fake_get):
        yield


def _client(role_name, username, email=""):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(username=username, password="x", role=role, email=email)
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_each_role_sees_only_its_own_forms(kobo):
    qa = _client(Role.QUAN_QA_RA, "cp_qa").get("/api/v1/kobo/forms/").json()
    assert [f["key"] for f in qa["forms"]] == ["questionnaire"]
    kii = _client(Role.KII_RA, "cp_kii")
    assert [f["key"] for f in kii.get("/api/v1/kobo/forms/").json()["forms"]] == ["kii"]
    assert kii.get("/api/v1/kobo/forms/questionnaire/submissions/").status_code == 403
    assert _client(Role.CONTACT_RA, "cp_ra").get("/api/v1/kobo/forms/").status_code == 403


@pytest.mark.django_db
def test_list_and_download_a_pdf(kobo):
    client = _client(Role.QUAN_QA_RA, "cp_dl")
    [row] = client.get("/api/v1/kobo/forms/questionnaire/submissions/").json()["results"]
    assert (row["id"], row["record"]) == (77, "SID-2026-000418")

    resp = client.get("/api/v1/kobo/forms/questionnaire/submissions/77/pdf/")
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    assert "Processor" in _text(resp.content)
    assert AuditEvent.objects.filter(action="kobo.submission_pdf_downloaded").exists()


@pytest.mark.django_db
def test_a_form_not_connected_says_so(kobo):
    resp = _client(Role.DOCUMENTARY_RA, "cp_doc").get("/api/v1/kobo/forms/documents/submissions/")
    assert resp.status_code == 503 and resp.json()["error"]["code"] == "kobo_not_configured"


@pytest.mark.django_db
def test_email_a_copy_to_myself(kobo):
    client = _client(Role.QUAN_QA_RA, "cp_me", email="qa.ra@example.org")
    resp = client.post("/api/v1/kobo/forms/questionnaire/submissions/77/email/", {"recipient": "me"}, format="json")

    assert resp.status_code == 200, resp.json()
    assert resp.json()["sent_to"] == "q***@example.org"
    [message] = mail.outbox
    assert message.to == ["qa.ra@example.org"]
    assert message.attachments[0][0].endswith(".pdf") and message.attachments[0][2] == "application/pdf"
    event = AuditEvent.objects.get(action="kobo.submission_copy_emailed")
    assert "qa.ra@example.org" not in str(event.metadata)


@pytest.mark.django_db
def test_email_to_the_respondent_needs_their_address_and_consent(kobo, main_case, settings):
    main_case.sample_id = "SID-2026-000418"
    main_case.save(update_fields=["sample_id"])
    client = _client(Role.FIELD_COORDINATOR, "cp_fc", email="fc@example.org")
    url = "/api/v1/kobo/forms/questionnaire/submissions/77/email/"

    assert client.post(url, {"recipient": "respondent"}, format="json").json()["error"]["code"] == "no_consent"
    record_consent(sample_case=main_case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
                   information_sheet_version="v1.2", method=ConsentMethod.WEB_CLICKTHROUGH)
    assert client.post(url, {"recipient": "respondent"}, format="json").json()["error"]["code"] == "no_email"

    Respondent.objects.create(sample_case=main_case, full_name="Tendai", is_eligible=True, email="tendai@example.org")
    resp = client.post(url, {"recipient": "respondent"}, format="json")
    assert resp.status_code == 200
    assert mail.outbox[-1].to == ["tendai@example.org"]
    assert "score" in mail.outbox[-1].body and "no score" in mail.outbox[-1].body


@pytest.mark.django_db
def test_no_typed_in_addresses_read_only_roles_or_unconfigured_email(kobo, settings):
    client = _client(Role.QUAN_QA_RA, "cp_x", email="qa@example.org")
    url = "/api/v1/kobo/forms/questionnaire/submissions/77/email/"
    assert client.post(url, {"recipient": "someone@elsewhere.com"}, format="json").status_code == 400
    supervisor = _client(Role.SUPERVISOR_READONLY, "cp_sup", email="sup@example.org")
    assert supervisor.post(url, {"recipient": "me"}, format="json").status_code == 403
    kii = _client(Role.FIELD_COORDINATOR, "cp_fc2", email="fc2@example.org")
    assert kii.post("/api/v1/kobo/forms/kii/submissions/77/email/", {"recipient": "respondent"}, format="json").status_code == 400

    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = ""
    resp = client.post(url, {"recipient": "me"}, format="json")
    assert resp.status_code == 503 and resp.json()["error"]["code"] == "email_not_configured"
    assert mail.outbox == []


@pytest.mark.django_db
def test_kobo_being_down_is_a_clear_error_not_a_crash(settings):
    import requests

    settings.KOBO_API_TOKEN, settings.KOBO_ASSET_UID = "token", "q-asset"
    client = _client(Role.QUAN_QA_RA, "cp_down")
    with patch("apps.kobo.submission_copies.requests.get", side_effect=requests.ConnectionError("down")):
        resp = client.get("/api/v1/kobo/forms/questionnaire/submissions/")
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "kobo_unreachable"
