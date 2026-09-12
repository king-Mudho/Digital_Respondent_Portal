"""
docs/22_TESTING_STRATEGY.md: "each threshold in docs/15_QA_AND_DATA_QUALITY.md
has a hard-stop and a soft-flag test case; confirm a hard stop never
auto-resolves without a human QAEvent."
"""

import json
import os

import pytest
from django.conf import settings
from django.utils import timezone

from apps.kobo.models import AdministrationMode, QAStatus, QUANSubmission
from apps.qa.models import QADecision, QAEvent, QARuleThreshold
from apps.qa.services import evaluate_submission, record_human_decision, seed_default_thresholds


@pytest.fixture(autouse=True)
def default_thresholds(db):
    return seed_default_thresholds()


def _make_submission(main_case, *, completion_seconds=1800, payload=None, uuid="sub-1"):
    payload = payload if payload is not None else {"sample_id": main_case.sample_id}
    os.makedirs(os.path.join(settings.MEDIA_ROOT, "kobo_submissions"), exist_ok=True)
    ref = f"kobo_submissions/{uuid}.json"
    with open(os.path.join(settings.MEDIA_ROOT, ref), "w", encoding="utf-8") as f:
        json.dump(payload, f)

    return QUANSubmission.objects.create(
        sample_case=main_case,
        kobo_submission_uuid=uuid,
        administration_mode=AdministrationMode.WEB_SELF,
        submitted_at=timezone.now(),
        completion_seconds=completion_seconds,
        raw_payload_ref=ref,
        qa_status=QAStatus.PENDING,
    )


# --- Duration plausibility (soft flag) --------------------------------------

def test_too_fast_submission_soft_flagged(main_case):
    submission = _make_submission(main_case, completion_seconds=60)
    triggered = evaluate_submission(submission)
    assert ("min_plausible_duration_seconds", False) in triggered
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.QUERY


def test_too_slow_submission_soft_flagged(main_case):
    submission = _make_submission(main_case, completion_seconds=6000)
    triggered = evaluate_submission(submission)
    assert ("max_plausible_duration_seconds", False) in triggered


def test_plausible_duration_not_flagged(main_case):
    submission = _make_submission(main_case, completion_seconds=900)
    triggered = evaluate_submission(submission)
    assert triggered == []
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.PENDING  # unchanged, not auto-passed


# --- Missing required fields (hard stop) ------------------------------------

def test_missing_required_field_is_hard_stop(main_case):
    QARuleThreshold.objects.filter(code="required_field_names").update(
        value=["turnover_band"]
    )
    submission = _make_submission(main_case, payload={"sample_id": main_case.sample_id})
    triggered = evaluate_submission(submission)
    assert ("hard_stop_missing_required_fields", True) in triggered
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.QUERY  # blocked, never auto QA_PASSED


def test_present_required_field_not_flagged(main_case):
    QARuleThreshold.objects.filter(code="required_field_names").update(
        value=["turnover_band"]
    )
    submission = _make_submission(
        main_case, payload={"sample_id": main_case.sample_id, "turnover_band": "medium"}
    )
    triggered = evaluate_submission(submission)
    assert not any(code == "hard_stop_missing_required_fields" for code, _ in triggered)


# --- Missing optional fields percent (soft flag) ----------------------------

def test_missing_optional_fields_over_threshold_soft_flagged(main_case):
    QARuleThreshold.objects.filter(code="optional_field_names").update(
        value=["q1", "q2", "q3", "q4"]
    )
    submission = _make_submission(main_case, payload={"sample_id": main_case.sample_id, "q1": "x"})
    triggered = evaluate_submission(submission)
    assert ("max_missing_optional_fields_percent", False) in triggered


def test_missing_optional_fields_under_threshold_not_flagged(main_case):
    QARuleThreshold.objects.filter(code="optional_field_names").update(
        value=["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10"]
    )
    submission = _make_submission(
        main_case,
        payload={f"q{i}": "x" for i in range(1, 10)} | {"sample_id": main_case.sample_id},
    )
    triggered = evaluate_submission(submission)
    assert not any(code == "max_missing_optional_fields_percent" for code, _ in triggered)


# --- Duplicate Master_ID within window (soft flag) --------------------------

def test_duplicate_submission_within_window_soft_flagged(main_case):
    _make_submission(main_case, uuid="sub-a")
    second = _make_submission(main_case, uuid="sub-b")
    triggered = evaluate_submission(second)
    assert ("duplicate_master_id_window_hours", False) in triggered


# --- Human decision flow -----------------------------------------------------

def test_hard_stop_never_auto_resolves_without_human_qaevent(main_case):
    QARuleThreshold.objects.filter(code="required_field_names").update(value=["turnover_band"])
    submission = _make_submission(main_case)
    evaluate_submission(submission)
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.QUERY
    # No human QAEvent yet -- must not have reached QA_PASSED by itself.
    assert not QAEvent.objects.filter(submission=submission, reviewer__isnull=False, decision=QADecision.ACCEPT).exists()


def test_record_human_decision_requires_note(main_case):
    submission = _make_submission(main_case)
    with pytest.raises(ValueError):
        record_human_decision(submission=submission, reviewer=None, decision=QADecision.ACCEPT, note="")


def test_record_human_accept_moves_to_qa_passed(main_case):
    submission = _make_submission(main_case)
    record_human_decision(
        submission=submission, reviewer=None, decision=QADecision.ACCEPT, note="Reviewed, looks fine."
    )
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.QA_PASSED


def test_record_human_accept_advances_the_invitation_token_to_qa_passed(main_case):
    """Completes the token funnel (docs/10_INVITATION_AND_CONSENT.md) --
    reconciliation advances a token to SUBMITTED when the raw Kobo
    submission first arrives (test_kobo.py); QA_PASSED is the one stage
    only a human decision can reach."""
    from apps.invitations.models import TokenStatus
    from apps.invitations.services import issue_invitation

    _, _, token = issue_invitation(main_case)
    submission = _make_submission(main_case)
    record_human_decision(submission=submission, reviewer=None, decision=QADecision.ACCEPT, note="Looks fine.")
    token.refresh_from_db()
    assert token.status == TokenStatus.QA_PASSED


def test_record_human_reject_does_not_advance_the_invitation_token(main_case):
    from apps.invitations.models import TokenStatus
    from apps.invitations.services import issue_invitation

    _, _, token = issue_invitation(main_case)
    submission = _make_submission(main_case)
    record_human_decision(submission=submission, reviewer=None, decision=QADecision.REJECT, note="Duplicate.")
    token.refresh_from_db()
    assert token.status != TokenStatus.QA_PASSED


def test_record_human_reject(main_case):
    submission = _make_submission(main_case)
    record_human_decision(
        submission=submission, reviewer=None, decision=QADecision.REJECT, note="Duplicate entry confirmed by phone."
    )
    submission.refresh_from_db()
    assert submission.qa_status == QAStatus.REJECTED
