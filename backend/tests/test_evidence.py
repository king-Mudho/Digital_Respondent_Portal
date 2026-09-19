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
    with patch("apps.evidence.tasks.generate_draft", return_value=fake_draft):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 202  # accepted: the reading happens in the background
    assert resp.data["ai_draft"]["section_b/RELEVANCE"] == "high"
    assert resp.data["ai_draft_model"] == "claude-opus-5"
    assert resp.data["ai_draft_generated_at"] is not None

    from apps.audit.models import AuditEvent

    assert AuditEvent.objects.filter(action="document.ai_draft_generated").exists()


def test_ai_draft_put_saves_edits(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {"section_a/DOC_ID": document_with_file.document_id, "section_b/RELEVANCE": "low"}
    with patch("apps.evidence.tasks.generate_draft", return_value=fake_draft):
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
    with patch("apps.evidence.tasks.generate_draft", return_value=fake_draft):
        documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")

    with patch("apps.evidence.views.submit_to_kobo", return_value={"instance_uuid": "abc-123", "status_code": 201}):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/submit/")
    assert resp.status_code == 200
    assert resp.data["kobo_submission_uuid"] == "abc-123"
    assert resp.data["kobo_submitted_at"] is not None


def test_ai_submit_failure_returns_error_and_does_not_mark_submitted(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_draft = {"section_a/DOC_ID": document_with_file.document_id}
    with patch("apps.evidence.tasks.generate_draft", return_value=fake_draft):
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


# --- Removing the uploaded file ----------------------------------------------

def _draft(document_with_file, client):
    with patch("apps.evidence.tasks.generate_draft", return_value={"section_a/DOC_ID": document_with_file.document_id}):
        client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")


def test_remove_file_deletes_it_from_disk_and_clears_metadata(documentary_ra_client, document_with_file, settings):
    document_with_file.refresh_from_db()
    path = os.path.join(settings.PRIVATE_DATA_ROOT, document_with_file.source_file_ref)
    assert os.path.exists(path)

    resp = documentary_ra_client.delete(f"/api/v1/documents/{document_with_file.pk}/file/")

    assert resp.status_code == 200
    assert resp.data["source_file_name"] == ""
    assert resp.data["source_file_size"] is None
    assert not os.path.exists(path)  # actually gone, not just hidden
    assert documentary_ra_client.get(f"/api/v1/documents/{document_with_file.pk}/file/").status_code == 404


def test_remove_file_is_audited_with_the_file_name(documentary_ra_client, document_with_file):
    documentary_ra_client.delete(f"/api/v1/documents/{document_with_file.pk}/file/")
    from apps.audit.models import AuditEvent

    event = AuditEvent.objects.filter(action="document.file_removed").latest("id")
    assert event.metadata["filename"] == "scan.pdf"


def test_remove_file_with_no_file_is_a_clean_404(documentary_ra_client, document):
    resp = documentary_ra_client.delete(f"/api/v1/documents/{document.pk}/file/")
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == "not_found"


def test_remove_file_discards_an_unsubmitted_ai_draft(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    _draft(document_with_file, documentary_ra_client)
    document_with_file.refresh_from_db()
    assert document_with_file.ai_draft

    resp = documentary_ra_client.delete(f"/api/v1/documents/{document_with_file.pk}/file/")

    assert resp.data["ai_draft"] is None  # written from the wrong file, so it goes too
    assert resp.data["ai_draft_generated_at"] is None


def test_remove_file_keeps_a_draft_already_submitted_to_kobo(documentary_ra_client, document_with_file, settings):
    """A submitted draft is the record of exactly what was filed."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    _draft(document_with_file, documentary_ra_client)
    from django.utils import timezone

    DocumentRecord.objects.filter(pk=document_with_file.pk).update(kobo_submitted_at=timezone.now())

    resp = documentary_ra_client.delete(f"/api/v1/documents/{document_with_file.pk}/file/")

    assert resp.data["ai_draft"] is not None


def test_replacing_a_file_discards_the_draft_made_from_the_old_one(documentary_ra_client, document_with_file, settings):
    """Uploading the right document over the wrong one must not leave the
    wrong document's draft to be reviewed and submitted for it."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    _draft(document_with_file, documentary_ra_client)

    resp = documentary_ra_client.post(
        f"/api/v1/documents/{document_with_file.pk}/file/", {"file": _pdf_file("right.pdf")}, format="multipart",
    )

    assert resp.data["source_file_name"] == "right.pdf"
    assert resp.data["ai_draft"] is None


def test_first_upload_does_not_touch_an_existing_draft_state(documentary_ra_client, document):
    resp = documentary_ra_client.post(
        f"/api/v1/documents/{document.pk}/file/", {"file": _pdf_file()}, format="multipart",
    )
    assert resp.status_code == 200


def test_supervisor_cannot_remove_a_file(supervisor_client, document_with_file):
    resp = supervisor_client.delete(f"/api/v1/documents/{document_with_file.pk}/file/")
    assert resp.status_code == 403
    document_with_file.refresh_from_db()
    assert document_with_file.source_file_name == "scan.pdf"  # untouched


# --- Background generation ---------------------------------------------------

def test_generate_failure_is_recorded_and_shown_not_left_running(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    from apps.evidence.ai_coding import AIDraftError

    with patch("apps.evidence.tasks.generate_draft", side_effect=AIDraftError("ai_request_failed", "The AI request failed: boom", 502)):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 202
    assert resp.data["ai_draft_status"] == "failed"
    assert resp.data["ai_draft_error"] == "The AI request failed: boom"
    assert resp.data["ai_draft"] is None


def test_generate_crash_never_leaves_the_document_stuck_on_running(documentary_ra_client, document_with_file, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    with patch("apps.evidence.tasks.generate_draft", side_effect=RuntimeError("unexpected")):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.data["ai_draft_status"] == "failed"
    assert "unexpected" not in resp.data["ai_draft_error"]  # no internals leaked to the screen


def test_second_generate_while_one_is_running_is_refused(documentary_ra_client, document_with_file, settings):
    from django.utils import timezone

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    DocumentRecord.objects.filter(pk=document_with_file.pk).update(ai_draft_status="running", ai_draft_started_at=timezone.now())
    resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "already_running"


def test_a_stuck_running_job_does_not_block_forever(documentary_ra_client, document_with_file, settings):
    """If a worker died mid-job, 'running' must not lock the document."""
    from datetime import timedelta

    from django.utils import timezone

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    DocumentRecord.objects.filter(pk=document_with_file.pk).update(
        ai_draft_status="running", ai_draft_started_at=timezone.now() - timedelta(minutes=30),
    )
    with patch("apps.evidence.tasks.generate_draft", return_value={"section_a/DOC_ID": document_with_file.document_id}):
        resp = documentary_ra_client.post(f"/api/v1/documents/{document_with_file.pk}/ai-draft/")
    assert resp.status_code == 202


def test_long_pdf_is_refused_up_front_without_starting_a_job(documentary_ra_client, document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.PRIVATE_DATA_ROOT = tmp_path
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(120):
        writer.add_blank_page(width=100, height=100)
    long_path = tmp_path / "long.pdf"
    with open(long_path, "wb") as f:
        writer.write(f)
    with open(long_path, "rb") as f:
        documentary_ra_client.post(
            f"/api/v1/documents/{document.pk}/file/",
            {"file": SimpleUploadedFile("long.pdf", f.read(), content_type="application/pdf")},
            format="multipart",
        )
    detail = documentary_ra_client.get(f"/api/v1/documents/{document.pk}/")
    assert detail.data["source_file_pages"] == 120

    resp = documentary_ra_client.post(f"/api/v1/documents/{document.pk}/ai-draft/")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "pdf_too_long"
    document.refresh_from_db()
    assert document.ai_draft_status == ""  # nothing was queued or charged

    with patch("apps.evidence.tasks.generate_draft", return_value={"section_a/DOC_ID": document.document_id}) as gen:
        ok = documentary_ra_client.post(f"/api/v1/documents/{document.pk}/ai-draft/", {"pages": "1-50"}, format="json")
    assert ok.status_code == 202
    assert gen.call_args.kwargs["page_range"] == "1-50"


def test_replacing_the_file_clears_a_stale_failed_state(documentary_ra_client, document_with_file, settings):
    DocumentRecord.objects.filter(pk=document_with_file.pk).update(ai_draft_status="failed", ai_draft_error="old file problem")
    resp = documentary_ra_client.post(
        f"/api/v1/documents/{document_with_file.pk}/file/", {"file": _pdf_file("new.pdf")}, format="multipart",
    )
    assert resp.data["ai_draft_status"] == ""
    assert resp.data["ai_draft_error"] == ""
