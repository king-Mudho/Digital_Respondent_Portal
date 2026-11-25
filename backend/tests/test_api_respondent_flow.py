"""
API-level tests for the public respondent flow: invitation validation,
eligibility, consent, Kobo redirect. Mirrors the happy-path chain from
docs/22_TESTING_STRATEGY.md's E2E scenario, at the API layer.
"""

import pytest
from rest_framework.test import APIClient

from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.invitations.services import issue_invitation


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def issued_token(main_case):
    raw_token, raw_code, token = issue_invitation(main_case)
    return raw_token, raw_code, token


def test_validate_endpoint_returns_minimal_payload(client, issued_token):
    raw_token, _, _ = issued_token
    response = client.get(f"/api/v1/invitations/validate/?t={raw_token}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert "Test Organisation" in body["organisation_name_confirmation"]
    # Never leaks Sample_ID, stratum, or Reserve status (AGENTS.md ground rule 6).
    assert "sample_id" not in body
    assert "stratum" not in body


def test_link_page_uses_the_name_the_respondent_asked_for(client, main_case):
    """A respondent who doesn't want to be called by their employer's name (Econet Mutare, 25 Nov 2026) sees the name
    the PI recorded -- on the link page and in the thank-you -- while the organisation keeps its register name."""
    from apps.invitations.messages import build_messages
    from apps.messaging.thanks import _names
    from django.utils import timezone

    main_case.metadata = {**(main_case.metadata or {}), "addressed_as": "Delphine Birira"}
    main_case.save(update_fields=["metadata"])
    raw_token, _, _ = issue_invitation(main_case)
    body = client.get(f"/api/v1/invitations/validate/?t={raw_token}").json()
    assert body["organisation_name_confirmation"] == "Please confirm: is this Delphine Birira?"
    assert "Test Organisation" not in body["organisation_name_confirmation"]
    msgs = build_messages(sample_case=main_case, link="https://x/i/t", manual_code="ABC", expires_at=timezone.now())
    assert "Delphine Birira" in msgs["whatsapp"] and "Test Organisation" not in msgs["whatsapp"]
    assert _names(main_case)[0] == "Delphine Birira"
    main_case.organisation.refresh_from_db()
    assert main_case.organisation.name.startswith("Test Organisation")


def test_validate_endpoint_rejects_bad_token(client, db):
    response = client.get("/api/v1/invitations/validate/?t=garbage")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "token_invalid"


def test_eligibility_endpoint_eligible(client, issued_token):
    raw_token, _, _ = issued_token
    response = client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Jane Doe", "role_category": "CEO_MD",
    })
    assert response.status_code == 200
    assert response.json()["is_eligible"] is True


def test_eligibility_endpoint_ineligible(client, issued_token):
    raw_token, _, _ = issued_token
    response = client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Gatekeeper", "role_category": "RECEPTIONIST",
    })
    assert response.status_code == 200
    assert response.json()["is_eligible"] is False


def test_consent_endpoint_records_and_advances_token(client, issued_token):
    raw_token, _, token = issued_token
    response = client.post("/api/v1/consent/", {
        "token": raw_token,
        "consent_type": ConsentType.PARTICIPATION,
        "decision": ConsentDecision.GIVEN,
        "information_sheet_version": "v1.0",
        "method": ConsentMethod.WEB_CLICKTHROUGH,
    })
    assert response.status_code == 200
    token.refresh_from_db()
    from apps.invitations.models import TokenStatus
    assert token.status == TokenStatus.CONSENTED


def test_kobo_redirect_denied_without_consent(client, issued_token):
    raw_token, _, _ = issued_token
    response = client.get(f"/api/v1/kobo/redirect-url/?t={raw_token}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"


def test_full_happy_path_to_kobo_redirect(client, issued_token, settings):
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/TeStFoRm"
    raw_token, _, _ = issued_token

    validate_resp = client.get(f"/api/v1/invitations/validate/?t={raw_token}")
    assert validate_resp.status_code == 200

    eligibility_resp = client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Jane Doe", "role_category": "CEO_MD",
    })
    assert eligibility_resp.json()["is_eligible"] is True

    consent_resp = client.post("/api/v1/consent/", {
        "token": raw_token,
        "consent_type": ConsentType.PARTICIPATION,
        "decision": ConsentDecision.GIVEN,
        "information_sheet_version": "v1.0",
        "method": ConsentMethod.WEB_CLICKTHROUGH,
    })
    assert consent_resp.status_code == 200

    redirect_resp = client.get(
        f"/api/v1/kobo/redirect-url/?t={raw_token}&administration_mode=01&respondent_role_category=CEO_MD&consent_version=v1.0"
    )
    assert redirect_resp.status_code == 200
    assert redirect_resp.json()["kobo_form_url"].startswith("https://ee.kobotoolbox.org/x/TeStFoRm?")


def test_ineligible_respondent_never_reaches_kobo_redirect(client, issued_token):
    """docs/28: 'An ineligible respondent is routed to referral, never to
    the questionnaire.'

    The earlier version of this test screened out a receptionist and then
    asserted a 403 -- but it never gave consent, so it was really just
    re-testing the consent gate under an eligibility name, and passed even
    though eligibility was not enforced at all. This version gives consent
    first, which is what someone bypassing the frontend would do: the
    consent endpoint is AllowAny and takes only a valid token, so the
    eligibility screen the UI shows is not a control on its own.
    """
    raw_token, _, _ = issued_token
    client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Gatekeeper", "role_category": "RECEPTIONIST",
    })
    consent_resp = client.post("/api/v1/consent/", {
        "token": raw_token,
        "consent_type": ConsentType.PARTICIPATION,
        "decision": ConsentDecision.GIVEN,
        "information_sheet_version": "v1.0",
        "method": ConsentMethod.WEB_CLICKTHROUGH,
    })
    assert consent_resp.status_code == 200, "consent itself is not eligibility-gated"

    redirect_resp = client.get(f"/api/v1/kobo/redirect-url/?t={raw_token}")

    assert redirect_resp.status_code == 403
    assert redirect_resp.json()["error"]["code"] == "eligibility_required"


def test_eligible_respondent_identified_after_a_gatekeeper_can_still_proceed(client, issued_token, settings):
    """record_eligibility_check never overwrites a prior attempt, so a case
    screened through a gatekeeper first must not be permanently blocked
    once the right person is identified."""
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/TeStFoRm"  # never rely on a local .env
    raw_token, _, _ = issued_token
    client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Gatekeeper", "role_category": "RECEPTIONIST",
    })
    client.post("/api/v1/eligibility/", {
        "token": raw_token, "full_name": "Jane Doe", "role_category": "CEO_MD",
    })
    client.post("/api/v1/consent/", {
        "token": raw_token,
        "consent_type": ConsentType.PARTICIPATION,
        "decision": ConsentDecision.GIVEN,
        "information_sheet_version": "v1.0",
        "method": ConsentMethod.WEB_CLICKTHROUGH,
    })

    redirect_resp = client.get(f"/api/v1/kobo/redirect-url/?t={raw_token}")

    assert redirect_resp.status_code == 200


def test_locked_reserve_cannot_be_validated_for_invitation(client, locked_reserve_case):
    from apps.invitations.services import TokenNotInvitable
    from apps.invitations.services import issue_invitation as issue

    with pytest.raises(TokenNotInvitable):
        issue(locked_reserve_case)
