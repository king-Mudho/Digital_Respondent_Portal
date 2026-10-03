"""Research-clearance documents (apps/clearance): the admin register, and the respondent-facing screen that
lets someone who opens their invitation link check who approved this study before they answer anything.

The rule under test throughout: a document is invisible to a respondent unless a staff member explicitly
set is_public=True and it has an uploaded file -- the default must never leak, and a document that was
never made public must never be discoverable by guessing its id.
"""


import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.clearance.models import ClearanceDocument
from apps.invitations.services import issue_invitation


def _client(role_name):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(username=f"clr_{role_name.lower()}", password="x", role=role)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _pdf(name="letter.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake clearance letter", content_type="application/pdf")


@pytest.fixture
def pi(db):
    return _client(Role.PI_ADMIN)


@pytest.fixture
def token_for(main_case):
    def make():
        raw_token, _, _ = issue_invitation(main_case, issued_by=None)
        return raw_token
    return make


# --- Admin CRUD --------------------------------------------------------------------------------

def test_the_pi_creates_a_document_defaulting_to_not_public(pi):
    client, user = pi
    response = client.post("/api/v1/clearance-documents/", {
        "title": "Research Ethics Clearance Letter", "issuing_body": "Chinhoyi University of Technology",
        "document_type": "ETHICS_CLEARANCE", "reference_number": "Annex 19, Form GRSD 17 SEBS/06/2025",
        "issue_date": "2026-08-24",
    }, format="json")
    assert response.status_code == 201
    assert response.data["is_public"] is False and response.data["has_file"] is False
    event = AuditEvent.objects.get(action="clearance.document_created")
    assert event.user_id == user.id


@pytest.mark.parametrize("role", [Role.FIELD_COORDINATOR, Role.ANALYST, Role.CONTACT_RA, Role.DOCUMENTARY_RA, Role.SUPERVISOR_READONLY])
def test_only_the_pi_can_manage_the_register(role, pi):
    client, _ = _client(role)
    assert client.get("/api/v1/clearance-documents/").status_code == 403
    assert client.post("/api/v1/clearance-documents/", {"title": "x", "issuing_body": "x", "document_type": "OTHER"}, format="json").status_code == 403


def test_uploading_a_file_and_toggling_visibility_is_audited(pi):
    client, user = pi
    doc = ClearanceDocument.objects.create(title="Ministry approval", issuing_body="Ministry of Agriculture", document_type="INSTITUTIONAL_APPROVAL")
    response = client.post(f"/api/v1/clearance-documents/{doc.pk}/file/", {"file": _pdf()}, format="multipart")
    assert response.status_code == 200 and response.data["has_file"] is True

    response = client.patch(f"/api/v1/clearance-documents/{doc.pk}/", {"is_public": True}, format="json")
    assert response.status_code == 200 and response.data["is_public"] is True
    event = AuditEvent.objects.get(action="clearance.visibility_changed")
    assert event.metadata["is_public"] is True and event.user_id == user.id


def test_an_unsupported_file_type_is_refused(pi):
    client, _ = pi
    doc = ClearanceDocument.objects.create(title="x", issuing_body="x", document_type="OTHER")
    bad = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
    response = client.post(f"/api/v1/clearance-documents/{doc.pk}/file/", {"file": bad}, format="multipart")
    assert response.status_code == 400 and response.data["error"]["code"] == "unsupported_file_type"


def test_a_document_that_was_never_public_can_be_deleted(pi):
    client, _ = pi
    doc = ClearanceDocument.objects.create(title="Draft, not used", issuing_body="x", document_type="OTHER")
    assert client.delete(f"/api/v1/clearance-documents/{doc.pk}/").status_code == 204
    assert not ClearanceDocument.objects.filter(pk=doc.pk).exists()


def test_a_document_that_is_public_cannot_be_deleted_only_archived(pi):
    client, _ = pi
    doc = ClearanceDocument.objects.create(title="Ethics clearance", issuing_body="CUT", document_type="ETHICS_CLEARANCE", is_public=True)
    response = client.delete(f"/api/v1/clearance-documents/{doc.pk}/")
    assert response.status_code == 409 and response.data["error"]["code"] == "was_public"
    assert ClearanceDocument.objects.filter(pk=doc.pk).exists()
    # archiving is the correct path, and stays possible
    assert client.patch(f"/api/v1/clearance-documents/{doc.pk}/", {"active": False}, format="json").status_code == 200


def test_a_document_once_shown_to_a_respondent_cannot_be_deleted_even_after_being_made_private_again(pi, main_case):
    client, _ = pi
    doc = ClearanceDocument.objects.create(title="x", issuing_body="x", document_type="OTHER", is_public=True)
    AuditEvent.objects.create(action="clearance.file_viewed_by_respondent", object_type="ClearanceDocument", object_id=str(doc.pk), metadata={})
    doc.is_public = False
    doc.save(update_fields=["is_public"])
    response = client.delete(f"/api/v1/clearance-documents/{doc.pk}/")
    assert response.status_code == 409


# --- Respondent side -----------------------------------------------------------------------------

def test_a_respondent_sees_only_public_active_documents_with_a_file(token_for):
    ClearanceDocument.objects.create(title="Shown", issuing_body="CUT", document_type="ETHICS_CLEARANCE", is_public=True, file_ref="clearance/a.pdf", file_name="a.pdf")
    ClearanceDocument.objects.create(title="Not public", issuing_body="CUT", document_type="OTHER", is_public=False, file_ref="clearance/b.pdf", file_name="b.pdf")
    ClearanceDocument.objects.create(title="Archived", issuing_body="CUT", document_type="OTHER", is_public=True, active=False, file_ref="clearance/c.pdf", file_name="c.pdf")
    ClearanceDocument.objects.create(title="No file yet", issuing_body="CUT", document_type="OTHER", is_public=True)

    client = APIClient()
    response = client.get("/api/v1/respondent-clearance-documents/", {"t": token_for()})
    assert response.status_code == 200
    titles = [d["title"] for d in response.data["results"]]
    assert titles == ["Shown"]


def test_the_respondent_list_never_carries_internal_fields(token_for):
    ClearanceDocument.objects.create(title="Shown", issuing_body="CUT", document_type="ETHICS_CLEARANCE", is_public=True, file_ref="clearance/a.pdf", file_name="a.pdf")
    client = APIClient()
    row = client.get("/api/v1/respondent-clearance-documents/", {"t": token_for()}).data["results"][0]
    for hidden in ("is_public", "active", "file_ref", "file_name", "created_by", "document_type"):
        assert hidden not in row


def test_a_missing_or_invalid_token_is_refused_not_a_500(token_for):
    client = APIClient()
    assert client.get("/api/v1/respondent-clearance-documents/").status_code == 400
    assert client.get("/api/v1/respondent-clearance-documents/", {"t": "not-a-real-token"}).status_code == 400


def test_a_revoked_token_cannot_list_documents(token_for, main_case):
    from apps.invitations.models import InvitationToken
    from apps.invitations.services import revoke_token

    raw = token_for()
    revoke_token(InvitationToken.objects.get(sample_case=main_case), "test", revoked_by=None)
    client = APIClient()
    response = client.get("/api/v1/respondent-clearance-documents/", {"t": raw})
    assert response.status_code == 400 and response.data["error"]["code"] == "token_revoked"


def test_the_respondent_can_open_a_public_documents_file_and_it_is_audited(token_for, tmp_path, settings):
    settings.PRIVATE_DATA_ROOT = tmp_path
    (tmp_path / "clearance").mkdir()
    (tmp_path / "clearance" / "a.pdf").write_bytes(b"%PDF-1.4 real bytes")
    doc = ClearanceDocument.objects.create(title="Shown", issuing_body="CUT", document_type="ETHICS_CLEARANCE",
                                           is_public=True, file_ref="clearance/a.pdf", file_name="Ethics.pdf", file_content_type="application/pdf")
    client = APIClient()
    response = client.get(f"/api/v1/respondent-clearance-documents/{doc.pk}/file/", {"t": token_for()})
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"%PDF-1.4 real bytes"
    assert "inline" in response["Content-Disposition"]
    event = AuditEvent.objects.get(action="clearance.file_viewed_by_respondent")
    assert event.object_id == str(doc.pk)


def _real_file(tmp_path, settings, name="x.pdf"):
    """A document whose file genuinely exists on disk -- so a test refusing to serve it proves the permission
    check did the refusing, not a missing-file 404 that would happen anyway regardless of that check."""
    settings.PRIVATE_DATA_ROOT = tmp_path
    (tmp_path / "clearance").mkdir(exist_ok=True)
    (tmp_path / "clearance" / name).write_bytes(b"%PDF-1.4 real bytes on disk")
    return f"clearance/{name}"


def test_a_private_documents_file_404s_even_though_the_file_genuinely_exists_on_disk(token_for, tmp_path, settings):
    ref = _real_file(tmp_path, settings)
    private_doc = ClearanceDocument.objects.create(title="Private", issuing_body="x", document_type="OTHER", is_public=False, file_ref=ref, file_name="x.pdf")
    client = APIClient()
    token = token_for()
    real = client.get(f"/api/v1/respondent-clearance-documents/{private_doc.pk}/file/", {"t": token})
    made_up = client.get("/api/v1/respondent-clearance-documents/999999/file/", {"t": token})
    assert real.status_code == made_up.status_code == 404
    assert real.data["error"]["code"] == made_up.data["error"]["code"] == "not_found"


def test_an_archived_public_documents_file_is_refused_even_though_the_file_genuinely_exists_on_disk(token_for, tmp_path, settings):
    ref = _real_file(tmp_path, settings)
    doc = ClearanceDocument.objects.create(title="Archived", issuing_body="x", document_type="OTHER", is_public=True, active=False, file_ref=ref, file_name="x.pdf")
    client = APIClient()
    assert client.get(f"/api/v1/respondent-clearance-documents/{doc.pk}/file/", {"t": token_for()}).status_code == 404
