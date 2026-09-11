"""
docs/22_TESTING_STRATEGY.md: "given a mocked Kobo API response including an
edited submission (changed last_edited_at, same kobo_submission_uuid),
confirm the reconciliation job updates the existing QUANSubmission rather
than creating a duplicate or missing it -- this is the test that directly
proves the webhook-edit-blindspot design decision actually works."
"""

from unittest.mock import patch

import pytest

from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.kobo.models import QAStatus, QUANSubmission, ReconciliationTrigger
from apps.kobo.services import KoboRedirectDenied, build_redirect_url, reconcile


def _submission_payload(sample_id, **overrides):
    payload = {
        "_uuid": "kobo-uuid-1",
        "sample_id": sample_id,
        "administration_mode": "01",
        "start": "2026-09-01T08:00:00",
        "_submission_time": "2026-09-01T08:20:00",
        "turnover_band": "medium",
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


# --- Kobo redirect gating (docs/10: no redirect without GIVEN consent) -----

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


def test_build_redirect_url_succeeds_after_consent(main_case):
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
