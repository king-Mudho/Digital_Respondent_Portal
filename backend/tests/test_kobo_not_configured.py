"""
KoboToolbox not connected yet -- a state, not a failure.

Found 2026-09-14 in production, where KOBO_ASSET_UID and KOBO_API_TOKEN are
both empty:

- build_redirect_url() produced `https://kf.kobotoolbox.org/x/?d[...]`. A
  respondent who consented and tapped "Start the questionnaire" would have
  landed on Kobo's 404 page, with no way back into the study.
- The scheduled reconciliation called `/api/v2/assets//data/` every 15
  minutes, writing 125 ReconciliationLog error rows in a day, and the QA
  screen told staff "Last sync failed" about a form that was simply not
  connected.
- The Sync panel's endpoints used IsFieldCoordinatorOrAdmin, so the QUAN QA
  RA -- on whose screen the panel sits -- got a 403 from it.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.services import record_eligibility_check
from apps.invitations.services import issue_invitation
from apps.kobo.models import ReconciliationLog
from apps.kobo.services import KoboNotConfigured, build_redirect_url, reconcile
from apps.kobo.tasks import reconcile_kobo_submissions


@pytest.fixture
def unconfigured(settings):
    settings.KOBO_ASSET_UID = ""
    settings.KOBO_API_TOKEN = ""
    settings.KOBO_FORM_URL = ""


def _client_for(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(username=username, password="x", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _consented_eligible(main_case):
    record_eligibility_check(sample_case=main_case, full_name="Tendai Moyo", role_category="CEO_MD", is_eligible=True)
    record_consent(
        sample_case=main_case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.2", method=ConsentMethod.WEB_CLICKTHROUGH,
    )


def _build(main_case):
    return build_redirect_url(
        main_case, token_id=1, invitation_wave=1, administration_mode="01",
        respondent_role_category="CEO_MD", consent_version="v1.2",
    )


# --- the respondent's link ---------------------------------------------

def test_no_questionnaire_link_is_built_without_an_asset(unconfigured, main_case):
    _consented_eligible(main_case)

    with pytest.raises(KoboNotConfigured):
        _build(main_case)


def test_redirect_endpoint_says_unavailable_instead_of_linking_to_a_404(unconfigured, main_case):
    _consented_eligible(main_case)
    raw_token, _, _ = issue_invitation(main_case)

    resp = APIClient().get(f"/api/v1/kobo/redirect-url/?t={raw_token}")

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "questionnaire_unavailable"
    assert "kobo_form_url" not in resp.json()


def test_the_gates_are_still_checked_before_configuration(unconfigured, main_case):
    """An unconnected form must not change what an unconsented case is told:
    consent is refused on its own terms first."""
    raw_token, _, _ = issue_invitation(main_case)

    resp = APIClient().get(f"/api/v1/kobo/redirect-url/?t={raw_token}")

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "consent_required"


def test_a_connected_form_builds_the_link_on_the_form_url(settings, main_case):
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/AbCd1234/"
    _consented_eligible(main_case)

    url = _build(main_case)["kobo_form_url"]

    assert url.startswith("https://ee.kobotoolbox.org/x/AbCd1234?d[master_id]=")
    assert f"d[sample_id]={main_case.sample_id}" in url
    assert "d[consent_status]=GIVEN" in url


def test_the_asset_uid_alone_does_not_build_a_link(settings, main_case):
    """The link used to be built as kf.kobotoolbox.org/x/<asset_uid>, which
    is not where Kobo serves web forms -- every respondent would have hit a
    404 even with the asset correctly configured."""
    settings.KOBO_ASSET_UID, settings.KOBO_API_TOKEN, settings.KOBO_FORM_URL = "aBcDeF123", "token", ""
    _consented_eligible(main_case)

    with pytest.raises(KoboNotConfigured):
        _build(main_case)


def test_prefill_values_are_percent_encoded(settings, main_case):
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/AbCd1234?lang=en"
    _consented_eligible(main_case)

    url = build_redirect_url(
        main_case, token_id=1, invitation_wave=1, administration_mode="01",
        respondent_role_category="CEO_MD", consent_version="v1.2 & draft", ra_id="a/b",
    )["kobo_form_url"]

    assert "?lang=en&d[master_id]=" in url
    assert "d[consent_version]=v1.2%20%26%20draft" in url
    assert "d[ra_id]=a%2Fb" in url


# --- reconciliation ----------------------------------------------------

@pytest.mark.django_db
def test_scheduled_run_skips_quietly_and_writes_nothing(unconfigured):
    assert reconcile_kobo_submissions() is None
    assert ReconciliationLog.objects.count() == 0


@pytest.mark.django_db
def test_reconcile_refuses_rather_than_calling_a_malformed_url(unconfigured):
    with pytest.raises(KoboNotConfigured):
        reconcile()


@pytest.mark.django_db
def test_an_asset_alone_or_a_token_alone_is_not_configured(settings):
    settings.KOBO_ASSET_UID, settings.KOBO_API_TOKEN = "asset", ""
    with pytest.raises(KoboNotConfigured):
        reconcile()

    settings.KOBO_ASSET_UID, settings.KOBO_API_TOKEN = "", "token"
    with pytest.raises(KoboNotConfigured):
        reconcile()


@pytest.mark.django_db
def test_manual_sync_reports_not_connected(unconfigured):
    resp = _client_for(Role.PI_ADMIN, "nc_admin").post("/api/v1/kobo/reconcile/")

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "kobo_not_configured"
    assert ReconciliationLog.objects.count() == 0


@pytest.mark.django_db
def test_status_reports_configuration_separately_from_the_last_run(unconfigured):
    body = _client_for(Role.PI_ADMIN, "nc_status").get("/api/v1/kobo/reconciliation-status/").json()

    assert body["configured"] is False
    assert body["last_run"] is None


# --- who may use the Sync panel ----------------------------------------

@pytest.mark.django_db
def test_the_quan_qa_ra_can_use_the_sync_panel_on_its_own_screen(unconfigured):
    client = _client_for(Role.QUAN_QA_RA, "nc_qa_ra")

    assert client.get("/api/v1/kobo/reconciliation-status/").status_code == 200
    assert client.post("/api/v1/kobo/reconcile/").status_code == 503  # reached the view, not refused


@pytest.mark.django_db
def test_a_supervisor_can_see_sync_status_but_not_trigger_a_run(unconfigured):
    client = _client_for(Role.SUPERVISOR_READONLY, "nc_super")

    assert client.get("/api/v1/kobo/reconciliation-status/").status_code == 200
    assert client.post("/api/v1/kobo/reconcile/").status_code == 403


@pytest.mark.django_db
def test_a_kii_ra_cannot_use_the_sync_panel(unconfigured):
    client = _client_for(Role.KII_RA, "nc_kii")

    assert client.get("/api/v1/kobo/reconciliation-status/").status_code == 403
    assert client.post("/api/v1/kobo/reconcile/").status_code == 403
