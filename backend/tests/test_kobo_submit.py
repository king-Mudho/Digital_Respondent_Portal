"""
apps/evidence/kobo_submit.py -- the OpenRosa submission XML builder and the
POST to KoboToolbox. Live-verified once against the real Documents project
on 2026-09-17 (two test submissions created under DOC-ID
"TEST-DELETE-ME-0001", confirmed via the data API, then deleted -- 0
submissions before and after), which is where the root-element bug this
module now avoids was actually found: the OpenRosa endpoint on this
KoboToolbox deployment routes a submission by the root element's own id
matching the *asset UID*, not the XLSForm's id_string. Everything below is
mocked -- these tests pin that behaviour and the rest of the builder
without touching the live project on every test run.
"""

from unittest.mock import Mock, patch

import pytest

from apps.evidence.document_tool_schema import SCHEMA
from apps.evidence.kobo_submit import (
    KoboSubmitError,
    build_submission_xml,
    kobo_submit_is_configured,
    submit_to_kobo,
)
from apps.evidence.models import DocumentRecord
from apps.evidence.services import generate_document_id


@pytest.fixture
def document(db):
    return DocumentRecord.objects.create(
        document_id=generate_document_id(), title="Kobo submit test doc", document_type="PLATFORM",
    )


@pytest.fixture
def user(db):
    from apps.accounts.models import Role, User

    role, _ = Role.objects.get_or_create(name=Role.DOCUMENTARY_RA)
    return User.objects.create_user(username="submit_ra", password="testpass123", role=role)


def test_kobo_submit_is_configured(settings):
    settings.KOBO_ACCOUNT_USERNAME = ""
    assert kobo_submit_is_configured() is False
    settings.KOBO_ACCOUNT_USERNAME = "mudho"
    assert kobo_submit_is_configured() is True


def test_root_element_id_is_the_asset_uid_not_the_form_id_string(document, settings):
    """The exact bug found live: using SCHEMA["form_id"] (the XLSForm
    id_string) as the root id 404s against this deployment's OpenRosa
    endpoint. It must be the asset UID instead."""
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    xml = build_submission_xml(document, {}, submitted_by=None, instance_uuid="11111111-1111-1111-1111-111111111111")
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?><a3vpgw6T4FbZGjQqmUgBND id="a3vpgw6T4FbZGjQqmUgBND"')
    assert SCHEMA["form_id"] not in xml  # the id_string must not appear as the root tag


def test_build_submission_xml_includes_meta_fields(document, settings, user):
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    xml = build_submission_xml(document, {}, submitted_by=user, instance_uuid="22222222-2222-2222-2222-222222222222")
    assert "<coder_username>submit_ra</coder_username>" in xml
    assert "<device_id>abf-fst-research-portal</device_id>" in xml
    assert "<instanceID>uuid:22222222-2222-2222-2222-222222222222</instanceID>" in xml


def test_build_submission_xml_select_multiple_joined_with_space(document, settings):
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    answers = {"section_b/EVIDENCE_TYPE": ["policy_normative", "statistical"]}
    xml = build_submission_xml(document, answers, submitted_by=None, instance_uuid="33333333-3333-3333-3333-333333333333")
    assert "<EVIDENCE_TYPE>policy_normative statistical</EVIDENCE_TYPE>" in xml


def test_build_submission_xml_repeat_group(document, settings):
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    answers = {
        "section_j/metric_repeat": [
            {"METRIC_NAME": "financial_inclusion", "value": "84", "unit_currency": "percent"},
            {"METRIC_NAME": "post_harvest_losses", "value": "40", "unit_currency": "percent"},
        ]
    }
    xml = build_submission_xml(document, answers, submitted_by=None, instance_uuid="44444444-4444-4444-4444-444444444444")
    assert xml.count("<metric_repeat>") == 2
    assert "<METRIC_NAME>financial_inclusion</METRIC_NAME>" in xml
    assert "<METRIC_NAME>post_harvest_losses</METRIC_NAME>" in xml


def test_build_submission_xml_rejects_doc_id_mismatch(document, settings):
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    answers = {"section_a/DOC_ID": "DOC-9999"}  # document.document_id is something else
    with pytest.raises(KoboSubmitError) as exc:
        build_submission_xml(document, answers, submitted_by=None, instance_uuid="55555555-5555-5555-5555-555555555555")
    assert exc.value.code == "doc_id_mismatch"


def test_submit_to_kobo_not_configured(document, settings, user):
    settings.KOBO_ACCOUNT_USERNAME = ""
    with pytest.raises(KoboSubmitError) as exc:
        submit_to_kobo(document, {}, user=user)
    assert exc.value.code == "kobo_submit_not_configured"


def test_submit_to_kobo_success(document, settings, user):
    settings.KOBO_ACCOUNT_USERNAME = "mudho"
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    mock_response = Mock(status_code=201, text="<OpenRosaResponse/>")
    with patch("apps.evidence.kobo_submit.requests.post", return_value=mock_response) as mock_post:
        result = submit_to_kobo(document, {}, user=user)
    assert "instance_uuid" in result
    assert result["status_code"] == 201
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://kc.kobotoolbox.org/mudho/submission"
    assert "files" in mock_post.call_args.kwargs


def test_submit_to_kobo_rejected_raises(document, settings, user):
    settings.KOBO_ACCOUNT_USERNAME = "mudho"
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    mock_response = Mock(status_code=404, text='{"detail":"Not found."}')
    with patch("apps.evidence.kobo_submit.requests.post", return_value=mock_response):
        with pytest.raises(KoboSubmitError) as exc:
            submit_to_kobo(document, {}, user=user)
    assert exc.value.code == "kobo_submission_rejected"


def test_submit_to_kobo_unreachable_raises(document, settings, user):
    import requests

    settings.KOBO_ACCOUNT_USERNAME = "mudho"
    settings.KOBO_DOCUMENTS_ASSET_UID = "a3vpgw6T4FbZGjQqmUgBND"
    with patch("apps.evidence.kobo_submit.requests.post", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(KoboSubmitError) as exc:
            submit_to_kobo(document, {}, user=user)
    assert exc.value.code == "kobo_unreachable"


# --- the view: a coding is submitted once -------------------------------------

def _api(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user)
    return client


def test_a_reviewed_draft_is_submitted_once_and_a_second_click_is_refused(document, user):
    document.ai_draft = {"section_a/DOC_ID": document.document_id}
    document.save()
    ok = {"instance_uuid": "abc-123", "status_code": 201}
    with patch("apps.evidence.views.submit_to_kobo", return_value=ok) as submit, \
         patch("apps.kobo.form_sync.sync_form") as sync:
        first = _api(user).post(f"/api/v1/documents/{document.pk}/ai-draft/submit/")
        second = _api(user).post(f"/api/v1/documents/{document.pk}/ai-draft/submit/")
    assert first.status_code == 200 and first.json()["kobo_submission_uuid"] == "abc-123"
    assert second.status_code == 409 and second.json()["error"]["code"] == "already_submitted"
    assert submit.call_count == 1  # the duplicate never reached KoboToolbox
    sync.assert_called_once()  # the portal's copy of the form was refreshed straight away


def test_a_failing_post_submission_sync_never_undoes_a_successful_submission(document, user):
    document.ai_draft = {"section_a/DOC_ID": document.document_id}
    document.save()
    with patch("apps.evidence.views.submit_to_kobo", return_value={"instance_uuid": "u1", "status_code": 201}), \
         patch("apps.kobo.form_sync.sync_form", side_effect=RuntimeError("boom")):
        resp = _api(user).post(f"/api/v1/documents/{document.pk}/ai-draft/submit/")
    document.refresh_from_db()
    assert resp.status_code == 200 and document.kobo_submitted_at is not None
