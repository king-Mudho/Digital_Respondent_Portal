"""
KII self-service invitation token lifecycle -- the KII equivalent of
test_invitations.py's coverage (generation entropy/format, hashing, expiry,
single-valid-token supersession, revocation), for the separate
KIIInvitationToken model (apps/kii/services.py docstring explains why it's
not a shared InvitationToken).
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.kii.models import KIIInvitationTokenStatus
from apps.kii.services import (
    KIITokenValidationError,
    create_kii_record,
    issue_kii_invitation,
    revoke_kii_invitation,
    validate_kii_manual_code,
    validate_kii_token,
)


@pytest.fixture
def kii_record(db):
    return create_kii_record(
        stakeholder_category="Financial institution representative",
        participant_name="Dr. T. Moyo",
        participant_role="Head of SME Lending",
        phone="0712 345 678",
        whatsapp_number="0712 345 678",
        email="tmoyo@example.org",
    )


def test_issue_kii_invitation_returns_valid_token(kii_record):
    raw_token, raw_code, token = issue_kii_invitation(kii_record)
    assert len(raw_token) > 32
    resolved = validate_kii_token(raw_token)
    assert resolved.pk == token.pk


def test_issue_kii_invitation_starts_at_sent_not_generated(kii_record):
    _, _, token = issue_kii_invitation(kii_record)
    assert token.status == KIIInvitationTokenStatus.SENT


def test_validating_a_kii_token_marks_it_opened(kii_record):
    raw_token, _, token = issue_kii_invitation(kii_record)
    validate_kii_token(raw_token)
    token.refresh_from_db()
    assert token.status == KIIInvitationTokenStatus.OPENED


def test_revalidating_after_consent_does_not_regress_to_opened(kii_record):
    raw_token, _, token = issue_kii_invitation(kii_record)
    validate_kii_token(raw_token)
    from apps.kii.services import _advance_kii_token_status

    _advance_kii_token_status(token, KIIInvitationTokenStatus.CONSENTED)
    validate_kii_token(raw_token)  # re-validate after already consented
    token.refresh_from_db()
    assert token.status == KIIInvitationTokenStatus.CONSENTED


def test_raw_kii_token_never_persisted(kii_record):
    raw_token, _, token = issue_kii_invitation(kii_record)
    assert raw_token not in token.token_hash
    assert "$" in token.token_hash


def test_manual_code_also_validates(kii_record):
    _, raw_code, token = issue_kii_invitation(kii_record)
    resolved = validate_kii_manual_code(raw_code)
    assert resolved.pk == token.pk


def test_wrong_kii_token_is_rejected(kii_record):
    issue_kii_invitation(kii_record)
    with pytest.raises(KIITokenValidationError) as exc_info:
        validate_kii_token("not-a-real-token")
    assert exc_info.value.code == "token_invalid"


def test_issuing_new_kii_token_supersedes_prior(kii_record):
    raw_token_1, _, token_1 = issue_kii_invitation(kii_record)
    raw_token_2, _, token_2 = issue_kii_invitation(kii_record)

    token_1.refresh_from_db()
    assert token_1.status == KIIInvitationTokenStatus.EXPIRED

    with pytest.raises(KIITokenValidationError):
        validate_kii_token(raw_token_1)

    resolved = validate_kii_token(raw_token_2)
    assert resolved.pk == token_2.pk


def test_expired_kii_token_rejected(kii_record):
    raw_token, _, token = issue_kii_invitation(kii_record)
    token.expires_at = timezone.now() - timezone.timedelta(days=1)
    token.save(update_fields=["expires_at"])

    with pytest.raises(KIITokenValidationError) as exc_info:
        validate_kii_token(raw_token)
    assert exc_info.value.code == "token_expired"


def test_revoked_kii_token_rejected(kii_record):
    raw_token, _, token = issue_kii_invitation(kii_record)
    revoke_kii_invitation(token, "informant requested revocation")

    with pytest.raises(KIITokenValidationError) as exc_info:
        validate_kii_token(raw_token)
    assert exc_info.value.code == "token_revoked"


# --- API: the KII record page's "Invite" panel -------------------------------

@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="kii_invite_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_issue_endpoint_returns_raw_token_once(admin_client, kii_record):
    resp = admin_client.post("/api/v1/kii-invitations/", {"kii_id": kii_record.kii_id, "channel": "WHATSAPP"}, format="json")
    assert resp.status_code == 201, resp.data
    assert len(resp.data["raw_token"]) > 32
    assert resp.data["raw_manual_code"]
    assert resp.data["link"].startswith("https://research.agribizframework.com/ki/")


def test_issue_endpoint_requires_can_manage_kii(kii_record):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="contact_ra_kii_invite", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post("/api/v1/kii-invitations/", {"kii_id": kii_record.kii_id}, format="json")
    assert resp.status_code == 403


def test_list_endpoint_never_exposes_the_raw_token_or_its_hash(admin_client, kii_record):
    issue_kii_invitation(kii_record)
    resp = admin_client.get(f"/api/v1/kii-invitations/?kii_id={kii_record.kii_id}")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    entry = resp.data["results"][0]
    assert "token_hash" not in entry
    assert "manual_code_hash" not in entry
    assert entry["status"] == KIIInvitationTokenStatus.SENT


def test_revoke_endpoint_marks_token_revoked(admin_client, kii_record):
    _, _, token = issue_kii_invitation(kii_record)
    resp = admin_client.post(f"/api/v1/kii-invitations/{token.id}/revoke/", {"reason": "Issued in error"}, format="json")
    assert resp.status_code == 200
    token.refresh_from_db()
    assert token.status == KIIInvitationTokenStatus.REVOKED


# --- Public respondent-facing surface ----------------------------------------

def test_validate_endpoint_returns_the_participant_name(kii_record):
    raw_token, _, _ = issue_kii_invitation(kii_record)
    client = APIClient()
    resp = client.get(f"/api/v1/kii-invitations/validate/?t={raw_token}")
    assert resp.status_code == 200
    assert resp.data == {"status": "valid", "participant_name": "Dr. T. Moyo"}


def test_validate_endpoint_rejects_a_bad_token(db):
    client = APIClient()
    resp = client.get("/api/v1/kii-invitations/validate/?t=not-a-real-token")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "token_invalid"


def test_consent_endpoint_records_participation_consent_by_web_clickthrough(kii_record):
    from apps.consent.models import ConsentMethod

    raw_token, _, _ = issue_kii_invitation(kii_record)
    client = APIClient()
    resp = client.post("/api/v1/kii-consent/", {"token": raw_token, "decision": "GIVEN", "information_sheet_version": "v1.5"}, format="json")
    assert resp.status_code == 200, resp.data
    kii_record.refresh_from_db()
    assert kii_record.participation_consent is not None
    assert kii_record.participation_consent.method == ConsentMethod.WEB_CLICKTHROUGH
    assert kii_record.participation_consent.decision == "GIVEN"


def test_kobo_redirect_refuses_without_consent(kii_record, settings):
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/testform"
    raw_token, _, _ = issue_kii_invitation(kii_record)
    client = APIClient()
    resp = client.get(f"/api/v1/kii-invitations/kobo-redirect-url/?t={raw_token}")
    assert resp.status_code == 403
    assert resp.data["error"]["code"] == "consent_required"


def test_kobo_redirect_works_once_consent_is_given(kii_record, settings):
    """Mutation-tested: this gate was confirmed to actually refuse (test
    above) before this one was written to prove it also actually works."""
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/testform"
    raw_token, _, _ = issue_kii_invitation(kii_record)
    client = APIClient()
    client.post("/api/v1/kii-consent/", {"token": raw_token, "decision": "GIVEN"}, format="json")

    resp = client.get(f"/api/v1/kii-invitations/kobo-redirect-url/?t={raw_token}")
    assert resp.status_code == 200
    assert kii_record.kii_id in resp.data["kobo_form_url"]
    assert kii_record.participant_name not in resp.data["kobo_form_url"]


def test_kobo_redirect_not_configured(kii_record, settings):
    settings.KOBO_KII_FORM_URL = ""
    raw_token, _, _ = issue_kii_invitation(kii_record)
    client = APIClient()
    client.post("/api/v1/kii-consent/", {"token": raw_token, "decision": "GIVEN"}, format="json")

    resp = client.get(f"/api/v1/kii-invitations/kobo-redirect-url/?t={raw_token}")
    assert resp.status_code == 503
    assert resp.data["error"]["code"] == "kobo_not_configured"
