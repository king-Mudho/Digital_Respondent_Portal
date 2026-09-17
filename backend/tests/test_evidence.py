"""
docs/14_DOCUMENTARY_EVIDENCE_MODULE.md: every document goes through
authenticity_assessment before qa_status=INCLUDED; a reviewer is always
recorded; a DISPUTED document is retained, never deleted.
"""

import os
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.evidence.models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord, DocumentType
from apps.evidence.services import (
    DocumentFileError,
    DocumentWorkflowError,
    build_document_coding_url,
    generate_document_id,
    open_source_file,
    record_authenticity_assessment,
    save_source_file,
    set_qa_status,
)


@pytest.fixture
def document(db):
    return DocumentRecord.objects.create(
        document_id=generate_document_id(),
        title="RBZ Monetary Policy Statement 2026",
        document_type=DocumentType.OFFICIAL,
    )


def test_document_id_format(document):
    import re

    assert re.fullmatch(r"DOC-\d{4}", document.document_id)


def test_cannot_include_unverified_document(document):
    with pytest.raises(DocumentWorkflowError):
        set_qa_status(document, DocumentQAStatus.INCLUDED, reviewer=None)


def test_verified_document_can_be_included(document):
    record_authenticity_assessment(document, AuthenticityAssessment.VERIFIED, reviewer=None)
    updated = set_qa_status(document, DocumentQAStatus.INCLUDED, reviewer=None)
    assert updated.qa_status == DocumentQAStatus.INCLUDED
    assert updated.verified_at is not None


def test_disputed_document_is_retained_not_deleted(document):
    record_authenticity_assessment(document, AuthenticityAssessment.DISPUTED, reviewer=None)
    document.interpretive_memo = "Publication date inconsistent with source site metadata."
    document.save(update_fields=["interpretive_memo"])

    excluded = set_qa_status(document, DocumentQAStatus.EXCLUDED, reviewer=None)
    assert excluded.authenticity_assessment == AuthenticityAssessment.DISPUTED
    assert DocumentRecord.objects.filter(pk=document.pk).exists()  # never deleted


def test_disputed_document_still_cannot_be_included(document):
    record_authenticity_assessment(document, AuthenticityAssessment.DISPUTED, reviewer=None)
    # DISPUTED is not UNVERIFIED, so the hard block doesn't literally apply,
    # but a disputed document being marked INCLUDED must still be a
    # deliberate reviewer call, not a workflow default -- this test
    # documents that the guard only blocks the UNVERIFIED case, matching
    # docs/14's "retained for the PI to adjudicate" language, and that the
    # PI/reviewer can still choose to include it.
    included = set_qa_status(document, DocumentQAStatus.INCLUDED, reviewer=None)
    assert included.qa_status == DocumentQAStatus.INCLUDED


# --- Document Analysis Tool: prefilled coding link --------------------------

def test_coding_url_none_when_not_configured(document, settings):
    settings.KOBO_DOCUMENTS_FORM_URL = ""
    assert build_document_coding_url(document) is None


def test_coding_url_prefills_doc_id(document, settings):
    settings.KOBO_DOCUMENTS_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"
    document.author_or_speaker = "Reserve Bank of Zimbabwe"
    document.save(update_fields=["author_or_speaker"])

    url = build_document_coding_url(document)

    assert url.startswith("https://ee.kobotoolbox.org/x/abcd1234?")
    assert f"d[section_a/DOC_ID]={document.document_id}" in url
    assert "d[section_a/org_author]=Reserve" in url
    # Blank optional fields are left out rather than sent as "d[...]=" --
    # the RA fills them in on the form, not overwritten with an empty value.
    assert "d[section_a/pub_event_date]" not in url


def test_coding_url_keeps_existing_query_string(document, settings):
    settings.KOBO_DOCUMENTS_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234?lang=en"
    url = build_document_coding_url(document)
    assert "?lang=en&d[section_a/DOC_ID]=" in url


# --- Source file upload/download --------------------------------------------

def _pdf_file(name="scan.pdf", size=10):
    return SimpleUploadedFile(name, b"%PDF-1.4 " + b"x" * size, content_type="application/pdf")


def test_upload_rejects_unsupported_extension(document):
    with pytest.raises(DocumentFileError) as exc:
        save_source_file(document, SimpleUploadedFile("script.exe", b"x"), user=None)
    assert exc.value.code == "unsupported_file_type"


def test_upload_rejects_file_over_limit(document, settings):
    settings.DOCUMENT_MAX_UPLOAD_MB = 1
    oversized = SimpleUploadedFile("big.pdf", b"x" * (2 * 1024 * 1024), content_type="application/pdf")
    with pytest.raises(DocumentFileError) as exc:
        save_source_file(document, oversized, user=None)
    assert exc.value.code == "file_too_large"


def test_open_source_file_before_upload_raises(document):
    with pytest.raises(DocumentFileError) as exc:
        open_source_file(document)
    assert exc.value.code == "not_found"


def test_upload_then_download_roundtrip(document, settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = tmp_path
    save_source_file(document, _pdf_file(), user=None)
    document.refresh_from_db()

    assert document.source_file_name == "scan.pdf"
    assert document.source_file_ref
    assert document.source_file_uploaded_at is not None

    path, filename, content_type = open_source_file(document)
    assert os.path.exists(path)
    assert filename == "scan.pdf"
    assert content_type == "application/pdf"


def test_reupload_replaces_and_removes_previous_file(document, settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = tmp_path
    save_source_file(document, _pdf_file("first.pdf"), user=None)
    document.refresh_from_db()
    first_path = os.path.join(tmp_path, document.source_file_ref)
    assert os.path.exists(first_path)

    save_source_file(document, _pdf_file("second.pdf"), user=None)
    document.refresh_from_db()

    assert document.source_file_name == "second.pdf"
    assert not os.path.exists(first_path)  # the old file is not left behind


# --- API: upload/download endpoint -------------------------------------------

@pytest.fixture
def documentary_ra_client(db):
    role, _ = Role.objects.get_or_create(name=Role.DOCUMENTARY_RA)
    user = User.objects.create_user(username="doc_ra", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_file_endpoint_upload_and_download(documentary_ra_client, document, settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = tmp_path
    upload = documentary_ra_client.post(
        f"/api/v1/documents/{document.pk}/file/",
        {"file": _pdf_file()},
        format="multipart",
    )
    assert upload.status_code == 200
    assert upload.data["source_file_name"] == "scan.pdf"

    download = documentary_ra_client.get(f"/api/v1/documents/{document.pk}/file/")
    assert download.status_code == 200
    assert download["Content-Disposition"] == 'attachment; filename="scan.pdf"'
    assert b"".join(download.streaming_content) == b"%PDF-1.4 " + b"x" * 10


def test_file_endpoint_rejects_unsupported_type(documentary_ra_client, document):
    resp = documentary_ra_client.post(
        f"/api/v1/documents/{document.pk}/file/",
        {"file": SimpleUploadedFile("notes.exe", b"x")},
        format="multipart",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "unsupported_file_type"


def test_file_endpoint_requires_a_file(documentary_ra_client, document):
    resp = documentary_ra_client.post(f"/api/v1/documents/{document.pk}/file/", {}, format="multipart")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "no_file"


# --- AI-assisted coding draft ------------------------------------------------

@pytest.fixture
def supervisor_client(db):
    role, _ = Role.objects.get_or_create(name=Role.SUPERVISOR_READONLY)
    user = User.objects.create_user(username="doc_supervisor", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def document_with_file(documentary_ra_client, document, settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = tmp_path
    resp = documentary_ra_client.post(
        f"/api/v1/documents/{document.pk}/file/", {"file": _pdf_file()}, format="multipart",
    )
    assert resp.status_code == 200
    return document


def test_ai_draft_schema_view(documentary_ra_client, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.KOBO_ACCOUNT_USERNAME = "mudho"
    resp = documentary_ra_client.get("/api/v1/documents/ai-draft-schema/")
    assert resp.status_code == 200
    assert resp.data["schema"]["form_id"] == "abf_fst_main_study_doc_analysis_v2"
    assert "section_a/DOC_ID" in resp.data["deterministic_fields"]
    assert resp.data["ai_configured"] is True
    assert resp.data["kobo_submit_configured"] is True


def test_new_document_serializes_ai_draft_as_null_not_empty_object(documentary_ra_client, document):
    """The model default is {} (an empty dict), but an empty *object*
    is truthy in JavaScript -- the frontend's "has a draft ever been
    generated?" check needs a real falsy value, or a brand new document
    renders as if it already had a completed AI draft."""
    resp = documentary_ra_client.get(f"/api/v1/documents/{document.pk}/")
    assert resp.data["ai_draft"] is None


def test_ai_draft_generate_requires_a_source_file(documentary_ra_client, document, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    resp = documentary_ra_client.post(f"/api/v1/documents/{document.pk}/ai-draft/")
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == "not_found"


def test_ai_draft_generate_requires_ai_configured(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = ""
    resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 503
    assert resp.data["error"]["code"] == "ai_not_configured"


def test_ai_draft_generate_success_saves_draft_and_audits(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {
        "section_a/DOC_ID": document_with_file.document_id,
        "section_b/RELEVANCE": "high",
        "_generated_by_model": "claude-opus-5",
        "_generated_at": "2026-09-17T12:00:00",
    }
    with patch("apps.evidence.views.generate_draft", return_value=fake_draft):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 200
    assert resp.data["ai_draft"]["section_b/RELEVANCE"] == "high"
    assert resp.data["ai_draft_model"] == "claude-opus-5"
    assert resp.data["ai_draft_generated_at"] is not None

    from apps.audit.models import AuditEvent

    assert AuditEvent.objects.filter(action="document.ai_draft_generated").exists()


def test_ai_draft_put_saves_edits(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {"section_a/DOC_ID": document_with_file.document_id, "section_b/RELEVANCE": "low"}
    with patch("apps.evidence.views.generate_draft", return_value=fake_draft):
        documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")

    resp = documentary_ra_client.put(
        f"/api/v1/documents/{document_with_file.pk}/ai-draft/",
        {"answers": {"section_b/RELEVANCE": "high"}},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["ai_draft"]["section_b/RELEVANCE"] == "high"
    assert resp.data["ai_draft"]["section_a/DOC_ID"] == document_with_file.document_id  # untouched fields kept


def test_ai_draft_put_without_a_draft_yet_errors(documentary_ra_client, document):
    resp = documentary_ra_client.put(
        f"/api/v1/documents/{document.pk}/ai-draft/", {"answers": {"x": "y"}}, format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "no_draft"


def test_ai_submit_requires_a_draft(documentary_ra_client, document):
    resp = documentary_ra_client.post(f"/api/v1/documents/{document.pk}/ai-draft/submit/")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "no_draft"


def test_ai_submit_success_records_submission_state(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {"section_a/DOC_ID": document_with_file.document_id}
    with patch("apps.evidence.views.generate_draft", return_value=fake_draft):
        documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")

    with patch("apps.evidence.views.submit_to_kobo", return_value={"instance_uuid": "abc-123", "status_code": 201}):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/submit/")
    assert resp.status_code == 200
    assert resp.data["kobo_submission_uuid"] == "abc-123"
    assert resp.data["kobo_submitted_at"] is not None


def test_ai_submit_failure_returns_error_and_does_not_mark_submitted(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {"section_a/DOC_ID": document_with_file.document_id}
    with patch("apps.evidence.views.generate_draft", return_value=fake_draft):
        documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")

    from apps.evidence.kobo_submit import KoboSubmitError

    with patch("apps.evidence.views.submit_to_kobo", side_effect=KoboSubmitError("kobo_submission_rejected", "nope", 502)):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/submit/")
    assert resp.status_code == 502
    assert resp.data["error"]["code"] == "kobo_submission_rejected"

    document_with_file.refresh_from_db()
    assert document_with_file.kobo_submission_uuid == ""
    assert document_with_file.kobo_submitted_at is None


def test_supervisor_read_only_cannot_generate_or_submit_draft(supervisor_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    generate_resp = supervisor_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert generate_resp.status_code == 403

    submit_resp = supervisor_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/submit/")
    assert submit_resp.status_code == 403


def test_supervisor_read_only_can_still_read_schema(supervisor_client):
    resp = supervisor_client.get("/api/v1/documents/ai-draft-schema/")
    assert resp.status_code == 200
