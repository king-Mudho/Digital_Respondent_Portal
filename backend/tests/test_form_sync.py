"""
The portal's copy of all three KoboToolbox forms (apps/kobo/form_sync.py):
it matches Kobo, notices edits and deletions, and acts on what it finds.
"""

from unittest.mock import patch

import pytest
import requests
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.evidence.models import DocumentRecord
from apps.kii.models import CodingStatus
from apps.kii.services import create_kii_record
from apps.kobo.form_sync import form_status, sync_all, sync_form
from apps.kobo.models import FormSyncLog, KoboFormSubmission
from apps.kobo.services import KoboNotConfigured


@pytest.fixture
def configured(settings):
    settings.KOBO_API_TOKEN = "token"
    settings.KOBO_ASSET_UID = "q-asset"
    settings.KOBO_KII_ASSET_UID = "kii-asset"
    settings.KOBO_DOCUMENTS_ASSET_UID = "doc-asset"


def _doc_row(kobo_id, doc_id, uuid, answer="x"):
    return {"_id": kobo_id, "_submission_time": "2026-09-19T15:54:47", "_submitted_by": "mudho",
            "section_a/DOC_ID": doc_id, "meta/rootUuid": f"uuid:{uuid}", "_uuid": uuid, "section_b/note": answer}


def _kii_row(kobo_id, kii_id):
    return {"_id": kobo_id, "_submission_time": "2026-09-19T10:00:00", "part_a/KII_ID": kii_id,
            "meta/rootUuid": f"uuid:kii-{kobo_id}"}


def _pull(rows):
    return patch("apps.kobo.form_sync.KoboClient.fetch_submissions", return_value=rows)


@pytest.mark.django_db
def test_a_sync_stores_every_submission_and_a_second_one_changes_nothing(configured):
    rows = [_doc_row(1, "DOC-0001", "a"), _doc_row(2, "DOC-0002", "b")]
    with _pull(rows):
        first = sync_form("documents")
        second = sync_form("documents")
    assert (first.pulled, first.new, first.updated, first.removed) == (2, 2, 0, 0)
    assert (second.pulled, second.new, second.updated, second.removed) == (2, 0, 0, 0)
    stored = KoboFormSubmission.objects.get(form_key="documents", kobo_id=1)
    assert stored.record == "DOC-0001" and stored.submitted_by == "mudho"
    assert stored.payload["section_b/note"] == "x" and stored.kobo_uuid == "a"


@pytest.mark.django_db
def test_an_edit_in_kobo_is_picked_up_and_a_deletion_is_flagged(configured):
    with _pull([_doc_row(1, "DOC-0001", "a"), _doc_row(2, "DOC-0002", "b")]):
        sync_form("documents")
    with _pull([_doc_row(1, "DOC-0001", "a", answer="edited")]):
        log = sync_form("documents")
    assert (log.updated, log.removed) == (1, 1)
    edited = KoboFormSubmission.objects.get(form_key="documents", kobo_id=1)
    assert edited.payload["section_b/note"] == "edited" and edited.last_changed_at is not None
    gone = KoboFormSubmission.objects.get(form_key="documents", kobo_id=2)
    assert gone.removed_at is not None
    # ...and if it comes back it counts again
    with _pull([_doc_row(1, "DOC-0001", "a", answer="edited"), _doc_row(2, "DOC-0002", "b")]):
        sync_form("documents")
    gone.refresh_from_db()
    assert gone.removed_at is None


@pytest.mark.django_db
def test_kobo_being_down_records_a_failed_run_and_keeps_what_the_portal_has(configured):
    with _pull([_doc_row(1, "DOC-0001", "a")]):
        sync_form("documents")
    with patch("apps.kobo.form_sync.KoboClient.fetch_submissions", side_effect=requests.ConnectionError("down")):
        log = sync_form("documents")
    assert "ConnectionError" in log.error_message
    assert KoboFormSubmission.objects.filter(form_key="documents", removed_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_an_unconnected_form_is_skipped_not_an_error(configured, settings):
    settings.KOBO_KII_ASSET_UID = ""
    with pytest.raises(KoboNotConfigured):
        sync_form("kii")
    with _pull([_doc_row(1, "DOC-0001", "a")]):
        logs = sync_all()
    assert {log.form_key for log in logs} == {"questionnaire", "documents"}
    assert not FormSyncLog.objects.filter(form_key="kii").exists()


@pytest.mark.django_db
def test_a_completed_kii_guide_marks_that_interviews_coding_complete(configured):
    match = create_kii_record(stakeholder_category="Financial institution representative", participant_name="A",
                              participant_role="r", preferred_mode="PHONE")
    other = create_kii_record(stakeholder_category="Financial institution representative", participant_name="B",
                              participant_role="r", preferred_mode="PHONE")
    with _pull([_kii_row(5, match.kii_id), _kii_row(6, "KII-9999")]):
        sync_form("kii")
        sync_form("kii")  # idempotent
    match.refresh_from_db()
    other.refresh_from_db()
    assert match.coding_status == CodingStatus.COMPLETE
    assert other.coding_status == CodingStatus.NOT_STARTED
    assert AuditEvent.objects.filter(action="kii.coding_completed_from_kobo", object_id=str(match.pk)).count() == 1


@pytest.mark.django_db
def test_a_coding_deleted_in_kobo_unlocks_the_document_but_a_present_one_stays_locked(configured):
    user = User.objects.create_user(username="ds", password="x", role=Role.objects.get_or_create(name=Role.DOCUMENTARY_RA)[0])
    kept = DocumentRecord.objects.create(document_id="DOC-0001", title="Kept", kobo_submission_uuid="a", kobo_submitted_by=user)
    lost = DocumentRecord.objects.create(document_id="DOC-0002", title="Lost", kobo_submission_uuid="b", kobo_submitted_by=user)
    lost.kobo_submitted_at = kept.kobo_submitted_at = __import__("django.utils.timezone", fromlist=["now"]).now()
    lost.save()
    kept.save()
    with _pull([_doc_row(1, "DOC-0001", "a")]):
        sync_form("documents")
    kept.refresh_from_db()
    lost.refresh_from_db()
    assert kept.kobo_submitted_at is not None and kept.kobo_submission_uuid == "a"
    assert lost.kobo_submitted_at is None and lost.kobo_submission_uuid == "" and lost.kobo_submitted_by is None
    assert AuditEvent.objects.filter(action="document.kobo_submission_removed_in_kobo").count() == 1


@pytest.mark.django_db
def test_status_says_whether_the_portal_and_kobo_agree(configured):
    with _pull([_doc_row(1, "DOC-0001", "a")]):
        sync_form("documents")
    with patch("apps.kobo.submission_copies._kobo_get", return_value={"count": 1, "results": []}):
        assert form_status("documents")["in_sync"] is True
    with patch("apps.kobo.submission_copies._kobo_get", return_value={"count": 2, "results": []}):
        status = form_status("documents")
        assert status["in_sync"] is False and (status["kobo_count"], status["portal_count"]) == (2, 1)


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


@pytest.mark.django_db
def test_sync_api_is_scoped_to_the_roles_own_forms_and_closed_to_read_only(configured):
    docs = _client(Role.DOCUMENTARY_RA, "fs_doc")
    with _pull([_doc_row(1, "DOC-0001", "a")]), patch("apps.kobo.submission_copies._kobo_get", return_value={"count": 1}):
        body = docs.post("/api/v1/kobo/sync/", {}, format="json").json()
        assert [f["key"] for f in body["forms"]] == ["documents"] and body["forms"][0]["in_sync"] is True
        assert docs.post("/api/v1/kobo/sync/", {"form": "kii"}, format="json").status_code == 403
        assert _client(Role.SUPERVISOR_READONLY, "fs_sup").post("/api/v1/kobo/sync/", {}, format="json").status_code == 403
        assert _client(Role.CONTACT_RA, "fs_ra").post("/api/v1/kobo/sync/", {}, format="json").status_code == 403
        status = docs.get("/api/v1/kobo/sync/status/").json()
        assert [f["key"] for f in status["forms"]] == ["documents"]


@pytest.mark.django_db
def test_sync_api_when_kobo_is_down_is_a_clear_502(configured):
    with patch("apps.kobo.form_sync.KoboClient.fetch_submissions", side_effect=requests.ConnectionError("down")):
        resp = _client(Role.DOCUMENTARY_RA, "fs_down").post("/api/v1/kobo/sync/", {}, format="json")
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "kobo_unreachable"


@pytest.mark.django_db
def test_the_listing_marks_which_rows_the_portal_already_holds(configured):
    rows = [_doc_row(1, "DOC-0001", "a"), _doc_row(2, "DOC-0002", "b")]
    with _pull(rows):
        sync_form("documents")
    live = [dict(rows[0]), _doc_row(2, "DOC-0002", "b", answer="changed after the sync")]
    with patch("apps.kobo.submission_copies._kobo_get", return_value={"count": 2, "results": live}):
        result = _client(Role.DOCUMENTARY_RA, "fs_list").get("/api/v1/kobo/forms/documents/submissions/").json()
    assert {r["id"]: r["portal_copy"] for r in result["results"]} == {1: True, 2: False}
