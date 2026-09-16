"""
Invitation token lifecycle -- docs/22_TESTING_STRATEGY.md: "generation
entropy/format, hashing (raw token never persisted), expiry, single-valid-
token supersession, revocation, rate limiting."
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.invitations.models import TokenStatus
from apps.invitations.services import (
    TokenNotInvitable,
    TokenValidationError,
    issue_invitation,
    revoke_token,
    validate_manual_code,
    validate_token,
)


def test_issue_invitation_returns_valid_token(main_case):
    raw_token, raw_code, token = issue_invitation(main_case)
    assert len(raw_token) > 32  # 32 bytes base64url-encoded
    resolved = validate_token(raw_token)
    assert resolved.pk == token.pk


def test_issue_invitation_starts_at_sent_not_generated(main_case):
    """Regression: a token used to start at GENERATED, and nothing ever
    advanced it to SENT -- issuing IS sending in this system (there's no
    separate delivery-confirmation step), so ContactDashboardView's
    "Invitations Sent" count silently missed every freshly-issued token."""
    _, _, token = issue_invitation(main_case)
    assert token.status == TokenStatus.SENT


def test_validating_a_token_marks_it_opened(main_case):
    raw_token, _, token = issue_invitation(main_case)
    assert token.status == TokenStatus.SENT
    validate_token(raw_token)
    token.refresh_from_db()
    assert token.status == TokenStatus.OPENED


def test_revalidating_after_consent_does_not_regress_to_opened(main_case):
    """The respondent (or an RA re-checking a manual code) can revisit the
    link after already consenting -- _validate_common's OPENED-marking must
    not regress status backward through the funnel."""
    raw_token, _, token = issue_invitation(main_case)
    validate_token(raw_token)  # -> OPENED
    from apps.invitations.services import advance_token_status

    advance_token_status(token, TokenStatus.CONSENTED)
    validate_token(raw_token)  # re-validate after already consented
    token.refresh_from_db()
    assert token.status == TokenStatus.CONSENTED


def test_advance_token_status_never_moves_backward(main_case):
    from apps.invitations.services import advance_token_status

    _, _, token = issue_invitation(main_case)
    advance_token_status(token, TokenStatus.CONSENTED)
    advance_token_status(token, TokenStatus.OPENED)  # attempted regression
    token.refresh_from_db()
    assert token.status == TokenStatus.CONSENTED


def test_advance_token_status_never_advances_a_terminal_token(main_case):
    from apps.invitations.services import advance_token_status

    _, _, token = issue_invitation(main_case)
    revoke_token(token, "test")
    advance_token_status(token, TokenStatus.CONSENTED)
    token.refresh_from_db()
    assert token.status == TokenStatus.REVOKED


def test_raw_token_never_persisted(main_case):
    raw_token, _, token = issue_invitation(main_case)
    assert raw_token not in token.token_hash
    assert "$" in token.token_hash  # salt$digest


def test_manual_code_also_validates(main_case):
    _, raw_code, token = issue_invitation(main_case)
    resolved = validate_manual_code(raw_code)
    assert resolved.pk == token.pk


def test_wrong_token_is_rejected(main_case):
    issue_invitation(main_case)
    with pytest.raises(TokenValidationError) as exc_info:
        validate_token("not-a-real-token")
    assert exc_info.value.code == "token_invalid"


def test_issuing_new_token_supersedes_prior(main_case):
    raw_token_1, _, token_1 = issue_invitation(main_case)
    raw_token_2, _, token_2 = issue_invitation(main_case, invitation_wave=2)

    token_1.refresh_from_db()
    assert token_1.status == TokenStatus.EXPIRED

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token_1)
    assert exc_info.value.code in ("token_invalid", "token_expired")

    resolved = validate_token(raw_token_2)
    assert resolved.pk == token_2.pk


def test_expired_token_rejected(main_case):
    raw_token, _, token = issue_invitation(main_case)
    token.expires_at = timezone.now() - timezone.timedelta(days=1)
    token.save(update_fields=["expires_at"])

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token)
    assert exc_info.value.code == "token_expired"


def test_revoked_token_rejected(main_case):
    raw_token, _, token = issue_invitation(main_case)
    revoke_token(token, "respondent requested revocation")

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token(raw_token)
    assert exc_info.value.code == "token_revoked"


# --- Reserve lock enforcement at the invitation boundary --------------------

def test_cannot_issue_invitation_for_locked_reserve(locked_reserve_case):
    with pytest.raises(TokenNotInvitable):
        issue_invitation(locked_reserve_case)


def test_can_issue_invitation_for_activated_reserve(activated_reserve_case):
    raw_token, _, token = issue_invitation(activated_reserve_case)
    resolved = validate_token(raw_token)
    assert resolved.pk == token.pk


# --- API: the "Send Invitation" panel's backing endpoints -------------------

@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="invite_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_issue_endpoint_returns_raw_token_once(admin_client, main_case):
    resp = admin_client.post(
        "/api/v1/invitations/", {"sample_id": main_case.sample_id, "channel": "WHATSAPP", "invitation_wave": 1},
        format="json",
    )
    assert resp.status_code == 201
    assert len(resp.data["raw_token"]) > 32
    assert resp.data["raw_manual_code"]


def test_issue_response_names_the_whatsapp_chat_to_open(admin_client, main_case):
    from apps.contacts.models import Respondent

    body = {"sample_id": main_case.sample_id, "channel": "WHATSAPP", "invitation_wave": 1}
    resp = admin_client.post("/api/v1/invitations/", body, format="json")
    assert (resp.data["whatsapp_to"], resp.data["whatsapp_to_name"]) == ("", "")

    Respondent.objects.create(sample_case=main_case, full_name="Gatekeeper", phone="0712 000 111")
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", is_eligible=True,
                              whatsapp_number="+263 77 123 4567; 0712 999 888")
    resp = admin_client.post("/api/v1/invitations/", body, format="json")
    assert (resp.data["whatsapp_to"], resp.data["whatsapp_to_name"]) == ("263771234567", "Jane Doe")


def test_issue_endpoint_rejects_locked_reserve(admin_client, locked_reserve_case):
    resp = admin_client.post(
        "/api/v1/invitations/", {"sample_id": locked_reserve_case.sample_id, "channel": "WHATSAPP"}, format="json",
    )
    assert resp.status_code == 403
    assert resp.data["error"]["code"] == "not_invitable"


def test_list_endpoint_never_exposes_the_raw_token_or_its_hash(admin_client, main_case):
    issue_invitation(main_case)
    resp = admin_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    entry = resp.data["results"][0]
    assert "token_hash" not in entry
    assert "manual_code_hash" not in entry
    assert entry["status"] == TokenStatus.SENT
    assert entry["channel"] == "WHATSAPP"


def test_list_endpoint_requires_sample_id(admin_client):
    resp = admin_client.get("/api/v1/invitations/")
    assert resp.status_code == 400


def test_list_endpoint_orders_newest_first_after_supersession(admin_client, main_case):
    issue_invitation(main_case, invitation_wave=1)
    issue_invitation(main_case, invitation_wave=2)
    resp = admin_client.get(f"/api/v1/invitations/?sample_id={main_case.sample_id}")
    results = resp.data["results"]
    assert len(results) == 2
    assert results[0]["invitation_wave"] == 2
    assert results[0]["status"] == TokenStatus.SENT
    assert results[1]["invitation_wave"] == 1
    assert results[1]["status"] == TokenStatus.EXPIRED


def test_revoke_endpoint_marks_token_revoked(admin_client, main_case):
    _, _, token = issue_invitation(main_case)
    resp = admin_client.post(f"/api/v1/invitations/{token.id}/revoke/", {"reason": "Issued in error"}, format="json")
    assert resp.status_code == 200
    token.refresh_from_db()
    assert token.status == TokenStatus.REVOKED
    assert token.revoked_reason == "Issued in error"


@pytest.mark.django_db
@pytest.mark.parametrize("progress", ["ELIGIBILITY_PASSED", "CONSENTED", "SURVEY_STARTED"])
def test_a_new_invitation_expires_a_link_the_respondent_had_already_started(main_case, progress):
    from apps.invitations.models import TokenStatus
    from apps.invitations.services import TokenValidationError, issue_invitation, validate_token

    raw, _, token = issue_invitation(main_case)
    token.status = progress
    token.save(update_fields=["status"])

    issue_invitation(main_case, invitation_wave=2)

    token.refresh_from_db()
    assert token.status == TokenStatus.EXPIRED
    with pytest.raises(TokenValidationError):
        validate_token(raw)


def _issue(client, main_case, **extra):
    return client.post("/api/v1/invitations/", {"sample_id": main_case.sample_id, "channel": "EMAIL", **extra}, format="json")


def test_every_channel_gets_a_ready_message_with_the_link_code_and_contact_line(admin_client, main_case, settings):
    from apps.contacts.models import Respondent

    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", is_eligible=True,
                              phone="0712 999 888", whatsapp_number="0771234567", email="jane@example.org")
    data = _issue(admin_client, main_case, link_base="https://evil.example.com").data
    assert data["link"].startswith("https://research.agribizframework.com/i/")  # never a foreign site
    assert (data["whatsapp_to"], data["sms_to"], data["email_to"]) == ("263771234567", "263712999888", "jane@example.org")
    msgs = data["messages"]
    for key in ("whatsapp", "sms", "email_body"):
        assert data["link"] in msgs[key] and data["raw_manual_code"] in msgs[key], key
    assert "Questions: Happyson Saina, 0773943709, abffst.research.cut@gmail.com" in msgs["whatsapp"]
    assert msgs["email_body"].startswith("Dear Jane Doe,") and main_case.organisation.name in msgs["email_body"]
    assert "0773943709" in msgs["sms"]

    settings.DEBUG = False
    assert _issue(admin_client, main_case, link_base="http://localhost:3000").data["link"].startswith("https://research.")
    settings.DEBUG = True  # local development only
    assert _issue(admin_client, main_case, link_base="http://localhost:3000").data["link"].startswith("http://localhost:3000/i/")


def test_an_invitation_is_emailed_from_the_study_address_only_with_its_own_link(admin_client, main_case, settings):
    from django.core import mail

    from apps.audit.models import AuditEvent
    from apps.contacts.models import Respondent

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "ABF-FST Research <abffst.research.cut@gmail.com>"
    data = _issue(admin_client, main_case).data
    url = f"/api/v1/invitations/{data['token_id']}/send-email/"
    body = {"link": data["link"], "manual_code": data["raw_manual_code"]}

    assert admin_client.post(url, body, format="json").data["error"]["code"] == "no_email"
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", is_eligible=True, email="jane@example.org")
    data = _issue(admin_client, main_case).data  # a fresh invitation now that there is an address
    url = f"/api/v1/invitations/{data['token_id']}/send-email/"
    body = {"link": data["link"], "manual_code": data["raw_manual_code"]}

    forged = admin_client.post(url, {**body, "link": data["link"][:-3] + "xyz"}, format="json")
    assert forged.status_code == 400 and forged.data["error"]["code"] == "link_mismatch"
    wrong_code = admin_client.post(url, {**body, "manual_code": "AAAAAAAA"}, format="json")
    assert wrong_code.data["error"]["code"] == "link_mismatch"
    assert mail.outbox == []

    resp = admin_client.post(url, body, format="json")
    assert resp.status_code == 200 and resp.data["sent_to"] == "j***@example.org"
    [message] = mail.outbox
    assert message.to == ["jane@example.org"] and data["link"] in message.body
    assert message.subject == data["messages"]["email_subject"]
    event = AuditEvent.objects.get(action="invitation.emailed")
    assert "jane@example.org" not in str(event.metadata)

    # A superseded invitation can't be emailed any more.
    _issue(admin_client, main_case)
    assert admin_client.post(url, body, format="json").data["error"]["code"] == "invitation_not_open"
