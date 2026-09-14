"""
docs/22_TESTING_STRATEGY.md: "given a mocked Kobo API response including an
edited submission (changed last_edited_at, same kobo_submission_uuid),
confirm the reconciliation job updates the existing QUANSubmission rather
than creating a duplicate or missing it -- this is the test that directly
proves the webhook-edit-blindspot design decision actually works."
"""

from unittest.mock import Mock, patch

import pytest
import requests
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.services import record_eligibility_check
from apps.kobo.client import KoboClient
from apps.kobo.models import QAStatus, QUANSubmission, ReconciliationLog, ReconciliationTrigger
from apps.kobo.services import KoboRedirectDenied, build_redirect_url, reconcile


@pytest.fixture(autouse=True)
def connected_kobo(settings):
    """Every test here mocks Kobo's HTTP responses, i.e. describes a
    *connected* form. They previously passed with no asset ID or token at
    all, only because nothing checked -- which is how production ran the
    scheduled pull against `/api/v2/assets//data/` for a day. The
    unconfigured case has its own tests in test_kobo_not_configured.py."""
    settings.KOBO_ASSET_UID = "test-asset-uid"
    settings.KOBO_API_TOKEN = "test-api-token"
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/TeStFoRm"


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="kobo_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _submission_payload(sample_id, **overrides):
    payload = {
        "_uuid": "kobo-uuid-1",
        "sample_id": sample_id,
        "administration_mode": "01",
        "start": "2026-09-01T08:00:00",
        "_submission_time": "2026-09-01T08:20:00",
        "turnover_band": "medium",
        # As an interviewer's KoboCollect submission arrives: signed in.
        "_submitted_by": "enumerator1",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_reconcile_creates_new_submission(main_case):
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_submission_payload(main_case.sample_id)]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.new_submissions == 1
    assert log.updated_submissions == 0
    submission = QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1")
    assert submission.sample_case_id == main_case.id
    assert submission.qa_status == QAStatus.PENDING


@pytest.mark.django_db
def test_reconcile_advances_the_invitation_token_to_submitted(main_case):
    """Completes the token funnel (docs/10_INVITATION_AND_CONSENT.md) -- a
    new raw submission arriving is the only signal this system has that the
    respondent actually submitted, so it's also the only place SUBMITTED is
    ever reached."""
    from apps.invitations.models import TokenStatus
    from apps.invitations.services import issue_invitation

    _, _, token = issue_invitation(main_case)
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_submission_payload(main_case.sample_id)]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    token.refresh_from_db()
    assert token.status == TokenStatus.SUBMITTED


@pytest.mark.django_db
def test_reconcile_with_no_live_token_is_a_no_op_not_an_error(main_case):
    """A case can have submissions reconciled before any invitation was
    ever issued for it in this environment (e.g. seeded test data) --
    confirms this doesn't crash."""
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_submission_payload(main_case.sample_id)]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    assert log.new_submissions == 1


@pytest.mark.django_db
def test_reconcile_detects_edited_submission_same_uuid(main_case):
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_submission_payload(main_case.sample_id)]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    submission = QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1")
    submission.qa_status = QAStatus.QA_PASSED
    submission.save(update_fields=["qa_status"])
    original_hash = submission.payload_content_hash

    edited_payload = _submission_payload(main_case.sample_id, turnover_band="high")
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[edited_payload]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.new_submissions == 0
    assert log.updated_submissions == 1
    assert QUANSubmission.objects.filter(kobo_submission_uuid="kobo-uuid-1").count() == 1  # no duplicate

    submission.refresh_from_db()
    assert submission.payload_content_hash != original_hash
    assert submission.last_edited_at is not None
    # Re-entering QA review of the changed fields, not silently kept passed.
    assert submission.qa_status == QAStatus.PENDING


@pytest.mark.django_db
def test_reconcile_unchanged_submission_is_not_counted_as_updated(main_case):
    payload = _submission_payload(main_case.sample_id)
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.new_submissions == 0
    assert log.updated_submissions == 0
    assert QUANSubmission.objects.count() == 1


@pytest.mark.django_db
def test_reconcile_flags_sample_id_mismatch_never_drops_or_automatches():
    from apps.audit.models import AuditEvent

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[_submission_payload("SID-2026-999999")]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.mismatches_flagged == 1
    assert QUANSubmission.objects.count() == 0
    assert AuditEvent.objects.filter(action="kobo.reconciliation_sample_id_mismatch").exists()


# --- Pagination (Kobo API v2's data endpoint is paginated) -----------------

def test_fetch_submissions_follows_pagination_next_link(settings):
    settings.KOBO_API_BASE_URL = "https://kf.example.org"
    settings.KOBO_API_TOKEN = "test-token"
    settings.KOBO_ASSET_UID = "aXXXXXX"

    page1 = Mock(status_code=200)
    page1.json.return_value = {
        "count": 3,
        "next": "https://kf.example.org/api/v2/assets/aXXXXXX/data/?page=2",
        "previous": None,
        "results": [{"_uuid": "u1"}, {"_uuid": "u2"}],
    }
    page1.raise_for_status = Mock()
    page2 = Mock(status_code=200)
    page2.json.return_value = {"count": 3, "next": None, "previous": "...", "results": [{"_uuid": "u3"}]}
    page2.raise_for_status = Mock()

    client = KoboClient()
    with patch("apps.kobo.client.requests.get", side_effect=[page1, page2]) as mock_get:
        results = client.fetch_submissions()

    assert [r["_uuid"] for r in results] == ["u1", "u2", "u3"]
    assert mock_get.call_count == 2
    # The second request hits the exact `next` URL Kobo returned, not a
    # hand-rolled page-number guess.
    assert mock_get.call_args_list[1].args[0] == "https://kf.example.org/api/v2/assets/aXXXXXX/data/?page=2"


def test_fetch_submissions_single_page_stops_without_extra_request():
    page1 = Mock(status_code=200)
    page1.json.return_value = {"count": 1, "next": None, "previous": None, "results": [{"_uuid": "only"}]}
    page1.raise_for_status = Mock()

    client = KoboClient(base_url="https://kf.example.org", api_token="t", asset_uid="a1")
    with patch("apps.kobo.client.requests.get", return_value=page1) as mock_get:
        results = client.fetch_submissions()

    assert results == [{"_uuid": "only"}]
    assert mock_get.call_count == 1


# --- Graceful failure when Kobo itself is unreachable ----------------------

@pytest.mark.django_db
def test_reconcile_records_failed_run_when_kobo_unreachable():
    with patch(
        "apps.kobo.services.KoboClient.fetch_submissions",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    ):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.error_message
    assert "Connection refused" in log.error_message
    assert log.submissions_pulled == 0
    assert QUANSubmission.objects.count() == 0


@pytest.mark.django_db
def test_manual_reconcile_endpoint_returns_502_when_kobo_unreachable(admin_client):
    with patch(
        "apps.kobo.services.KoboClient.fetch_submissions",
        side_effect=requests.exceptions.Timeout("timed out"),
    ):
        resp = admin_client.post("/api/v1/kobo/reconcile/")
    assert resp.status_code == 502
    assert resp.data["error"]["code"] == "kobo_unreachable"


@pytest.mark.django_db
def test_manual_reconcile_endpoint_returns_200_on_success(admin_client, main_case):
    with patch(
        "apps.kobo.services.KoboClient.fetch_submissions",
        return_value=[_submission_payload(main_case.sample_id)],
    ):
        resp = admin_client.post("/api/v1/kobo/reconcile/")
    assert resp.status_code == 200
    assert resp.data["new_submissions"] == 1
    assert resp.data["error_message"] == ""


@pytest.mark.django_db
def test_reconciliation_status_view_returns_latest_log(admin_client):
    ReconciliationLog.objects.create(run_started_at="2026-09-01T08:00:00Z", triggered_by=ReconciliationTrigger.SCHEDULE)
    latest = ReconciliationLog.objects.create(
        run_started_at="2026-09-10T08:00:00Z", triggered_by=ReconciliationTrigger.MANUAL, submissions_pulled=5,
    )
    resp = admin_client.get("/api/v1/kobo/reconciliation-status/")
    assert resp.status_code == 200
    assert resp.data["configured"] is True
    assert resp.data["last_run"]["id"] == latest.pk
    assert resp.data["last_run"]["submissions_pulled"] == 5


@pytest.mark.django_db
def test_reconciliation_status_view_returns_null_when_never_run(admin_client):
    resp = admin_client.get("/api/v1/kobo/reconciliation-status/")
    assert resp.status_code == 200
    assert resp.data["configured"] is True
    assert resp.data["last_run"] is None


# --- Kobo redirect gating (docs/10: no redirect without a passed
# eligibility check AND GIVEN consent; both are enforced here) ------------

def _make_eligible(main_case):
    record_eligibility_check(
        sample_case=main_case, full_name="Jane Doe", role_category="CEO_MD", is_eligible=True
    )


def test_build_redirect_url_denied_without_consent(main_case):
    with pytest.raises(KoboRedirectDenied) as exc_info:
        build_redirect_url(
            main_case,
            token_id=1,
            invitation_wave=1,
            administration_mode="01",
            respondent_role_category="CEO_MD",
            consent_version="v1.0",
        )
    assert exc_info.value.code == "consent_required"


def test_build_redirect_url_denied_without_an_eligible_respondent(main_case):
    """Consent alone is not enough. Someone holding a valid token can POST
    /consent/ directly without ever passing the eligibility screen, so the
    eligibility check has to live here rather than in the frontend's
    routing (docs/28's "never to the questionnaire")."""
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )

    with pytest.raises(KoboRedirectDenied) as exc_info:
        build_redirect_url(
            main_case,
            token_id=1,
            invitation_wave=1,
            administration_mode="01",
            respondent_role_category="CEO_MD",
            consent_version="v1.0",
        )

    assert exc_info.value.code == "eligibility_required"


def test_build_redirect_url_denied_when_the_respondent_was_screened_out(main_case):
    record_eligibility_check(
        sample_case=main_case, full_name="Gatekeeper", role_category="", is_eligible=False
    )
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )

    with pytest.raises(KoboRedirectDenied) as exc_info:
        build_redirect_url(
            main_case,
            token_id=1,
            invitation_wave=1,
            administration_mode="01",
            respondent_role_category="CEO_MD",
            consent_version="v1.0",
        )

    assert exc_info.value.code == "eligibility_required"


def test_build_redirect_url_succeeds_after_eligibility_and_consent(main_case):
    _make_eligible(main_case)
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    result = build_redirect_url(
        main_case,
        token_id=1,
        invitation_wave=1,
        administration_mode="01",
        respondent_role_category="CEO_MD",
        consent_version="v1.0",
    )
    assert main_case.sample_id in result["kobo_form_url"]
    assert main_case.organisation.master_id in result["kobo_form_url"]


# --- Submissions started without the portal link (KoboCollect) ------------

@pytest.mark.django_db
def test_reconcile_matches_a_collect_submission_by_the_forms_own_sample_id(main_case):
    """Opened in KoboCollect, the r2 questionnaire's portal hidden fields are
    blank; the RA-entered Sample_ID arrives in SAMPLE_ID_FINAL instead.
    Before, such a submission could only ever be flagged as a mismatch."""
    payload = _submission_payload("", administration_mode="", ADMIN_MODE_FINAL="telephone")
    payload["SAMPLE_ID_FINAL"] = main_case.sample_id

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert log.new_submissions == 1 and log.mismatches_flagged == 0
    assert QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1").administration_mode == "03"


@pytest.mark.django_db
def test_the_portal_hidden_fields_win_over_the_forms_own_values(main_case):
    payload = _submission_payload(main_case.sample_id, administration_mode="02",
                                  SAMPLE_ID_FINAL="SID-2026-999999", ADMIN_MODE_FINAL="face_to_face")

    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    submission = QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1")
    assert submission.sample_case_id == main_case.id
    assert submission.administration_mode == "02"


# --- Timestamps and duration, as Kobo actually sends them ------------------

@pytest.mark.django_db
def test_kobo_submission_time_without_offset_is_read_as_utc(main_case):
    """Kobo sends `_submission_time` in UTC with no offset. Read as Harare
    time it landed two hours early, before the form was even started."""
    from datetime import datetime
    from datetime import timezone as tz

    payload = _submission_payload(
        main_case.sample_id,
        start="2026-09-14T15:44:30.060+02:00",
        end="2026-09-14T16:02:30.060+02:00",
        _submission_time="2026-09-14T14:03:21",
    )
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    submission = QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1")
    assert submission.submitted_at == datetime(2026, 9, 14, 14, 3, 21, tzinfo=tz.utc)
    assert submission.submitted_at > submission.started_at


@pytest.mark.django_db
def test_reconcile_records_completion_time_so_duration_rules_can_fire(main_case):
    from apps.qa.services import seed_default_thresholds

    seed_default_thresholds()
    payload = _submission_payload(
        main_case.sample_id,
        start="2026-09-14T15:44:30+02:00",
        end="2026-09-14T15:46:30+02:00",  # two minutes: under the 5-minute minimum
        _submission_time="2026-09-14T13:46:31",
    )
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    submission = QUANSubmission.objects.get(kobo_submission_uuid="kobo-uuid-1")
    assert submission.completion_seconds == 120
    assert submission.qa_status == QAStatus.QUERY


@pytest.mark.django_db
def test_an_unmatched_submission_is_audited_once_not_every_run():
    from apps.audit.models import AuditEvent

    payload = _submission_payload("SID-2026-999999")
    for _ in range(3):
        with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
            log = reconcile(triggered_by=ReconciliationTrigger.SCHEDULE)
        assert log.mismatches_flagged == 1  # still reported on every run

    assert AuditEvent.objects.filter(action="kobo.reconciliation_sample_id_mismatch").count() == 1


@pytest.mark.django_db
def test_an_edit_in_kobo_updates_the_submission_instead_of_duplicating_it(main_case):
    """KoboToolbox changes `_uuid` on every edit; `meta/rootUuid` is stable."""
    original = _submission_payload(main_case.sample_id, _uuid="first-uuid")
    original["meta/rootUuid"] = "uuid:first-uuid"
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[original]):
        reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    edited = _submission_payload(main_case.sample_id, _uuid="second-uuid", turnover_band="high")
    edited["meta/rootUuid"] = "uuid:first-uuid"
    edited["meta/deprecatedID"] = "uuid:first-uuid"
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[edited]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)

    assert (log.new_submissions, log.updated_submissions) == (0, 1)
    assert QUANSubmission.objects.count() == 1
    submission = QUANSubmission.objects.get()
    assert submission.kobo_submission_uuid == "first-uuid"
    assert submission.last_edited_at is not None


# --- Login-free submissions must come through the portal ---------------------

@pytest.mark.django_db
def test_a_login_free_submission_with_the_portal_signature_is_accepted(main_case):
    from apps.kobo.services import sign_portal_token

    payload = _submission_payload(main_case.sample_id, _submitted_by=None, portal_token_id=sign_portal_token(7, main_case.sample_id))
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    assert (log.new_submissions, log.mismatches_flagged) == (1, 0)


@pytest.mark.django_db
@pytest.mark.parametrize("portal_token_id", ["", "7", "7.0123456789abcdef0123456789abcdef"])
def test_a_login_free_submission_without_a_valid_signature_is_set_aside(main_case, portal_token_id):
    """Someone with the public form link typing a real Sample_ID."""
    from apps.audit.models import AuditEvent

    payload = _submission_payload(main_case.sample_id, _submitted_by=None, portal_token_id=portal_token_id)
    for _ in range(2):
        with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
            log = reconcile(triggered_by=ReconciliationTrigger.SCHEDULE)
        assert (log.new_submissions, log.mismatches_flagged) == (0, 1)
    assert QUANSubmission.objects.count() == 0
    assert AuditEvent.objects.filter(action="kobo.reconciliation_unverified_submission").count() == 1


@pytest.mark.django_db
def test_a_signature_for_one_case_does_not_work_for_another(main_case, organisation, stratum):
    from apps.kobo.services import sign_portal_token
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_sample_case

    other = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    payload = _submission_payload(main_case.sample_id, _submitted_by=None, portal_token_id=sign_portal_token(7, other.sample_id))
    with patch("apps.kobo.services.KoboClient.fetch_submissions", return_value=[payload]):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)
    assert log.new_submissions == 0
