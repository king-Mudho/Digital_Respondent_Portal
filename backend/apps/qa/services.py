"""
Hard-stop vs. soft-flag QA evaluation (docs/15_QA_AND_DATA_QUALITY.md).

A hard stop blocks a submission from reaching QA_PASSED until corrected or
explicitly overridden by a human reviewer with a note. A soft flag places
the submission in the QA queue for reviewer judgement but doesn't block
progress by itself. Only a human-recorded QAEvent.decision=ACCEPT ever moves
qa_status to QA_PASSED -- never automatic, even when zero rules triggered.

Two threshold codes -- `logic_violation_hard_stop_rules` and
`logic_violation_soft_flag_rules` -- are seeded empty. docs/15 says these
are meant to be "seeded from the Kobo form's own skip-logic definition"
(hard-stop) and "PI-defined per question" (soft-flag); neither can be
populated for real until a real Kobo form/asset exists (see the Phase 3
open item in docs/27_AGENT_EXECUTION_PLAN.md). The evaluator below still
runs them as a no-op extension point so wiring in real rules later needs no
structural change here.
"""

import json
import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import advance_token_status
from apps.kobo.models import QAStatus, QUANSubmission

from .models import QADecision, QAEvent, QARuleThreshold

# Seeded defaults per docs/15_QA_AND_DATA_QUALITY.md -- "proposed engineering
# defaults, not yet PI-confirmed research decisions", proceeding on them per
# the user's Phase-0-defaults decision (docs/27_AGENT_EXECUTION_PLAN.md).
DEFAULT_THRESHOLDS = {
    "min_plausible_duration_seconds": 300,
    "max_plausible_duration_seconds": 5400,
    "max_missing_optional_fields_percent": 10,
    "duplicate_master_id_window_hours": 24,
    "logic_violation_hard_stop_rules": [],
    "logic_violation_soft_flag_rules": [],
    "mode_imbalance_alert_ratio": 0.70,
    # Not in docs/15's table by name, but required to make
    # hard_stop_missing_required_fields and max_missing_optional_fields_percent
    # concretely evaluable before the real Kobo form's field list is frozen.
    "required_field_names": [],
    "optional_field_names": [],
}


def seed_default_thresholds(set_by=None) -> list[QARuleThreshold]:
    now = timezone.now()
    created = []
    for code, value in DEFAULT_THRESHOLDS.items():
        threshold, _ = QARuleThreshold.objects.get_or_create(
            code=code, defaults={"value": value, "effective_from": now, "set_by": set_by}
        )
        created.append(threshold)
    return created


def _load_thresholds() -> dict:
    return {t.code: t.value for t in QARuleThreshold.objects.all()}


def _load_payload(submission: QUANSubmission) -> dict:
    if not submission.raw_payload_ref:
        return {}
    path = os.path.join(settings.MEDIA_ROOT, submission.raw_payload_ref)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_submission(submission: QUANSubmission) -> list[tuple[str, bool]]:
    """Evaluate every active QARuleThreshold against a submission. Creates a
    QAEvent (reviewer=None -- an automated flag, not a human decision) for
    each triggered rule, and sets qa_status=QUERY if anything triggered.
    Returns [(rule_code, is_hard_stop), ...].
    """
    thresholds = _load_thresholds()
    payload = _load_payload(submission)
    triggered: list[tuple[str, bool]] = []

    required_fields = thresholds.get("required_field_names") or []
    missing_required = [f for f in required_fields if not payload.get(f)]
    if missing_required:
        triggered.append(("hard_stop_missing_required_fields", True))

    min_dur = thresholds.get("min_plausible_duration_seconds")
    if min_dur is not None and submission.completion_seconds is not None and submission.completion_seconds < min_dur:
        triggered.append(("min_plausible_duration_seconds", False))

    max_dur = thresholds.get("max_plausible_duration_seconds")
    if max_dur is not None and submission.completion_seconds is not None and submission.completion_seconds > max_dur:
        triggered.append(("max_plausible_duration_seconds", False))

    optional_fields = thresholds.get("optional_field_names") or []
    max_missing_pct = thresholds.get("max_missing_optional_fields_percent")
    if optional_fields and max_missing_pct is not None:
        missing_count = sum(1 for f in optional_fields if not payload.get(f))
        missing_pct = (missing_count / len(optional_fields)) * 100
        if missing_pct > max_missing_pct:
            triggered.append(("max_missing_optional_fields_percent", False))

    window_hours = thresholds.get("duplicate_master_id_window_hours")
    if window_hours is not None:
        window_start = submission.submitted_at - timedelta(hours=window_hours)
        duplicate_exists = (
            QUANSubmission.objects.filter(
                sample_case__organisation=submission.sample_case.organisation,
                submitted_at__gte=window_start,
                submitted_at__lt=submission.submitted_at,
            )
            .exclude(pk=submission.pk)
            .exists()
        )
        if duplicate_exists:
            triggered.append(("duplicate_master_id_window_hours", False))

    # Extension points -- no-op until real rules are seeded (see module docstring).
    for rule in thresholds.get("logic_violation_hard_stop_rules") or []:
        triggered.append((rule.get("code", "logic_violation_hard_stop"), True))
    for rule in thresholds.get("logic_violation_soft_flag_rules") or []:
        triggered.append((rule.get("code", "logic_violation_soft_flag"), False))

    for rule_code, is_hard_stop in triggered:
        QAEvent.objects.create(
            submission=submission,
            rule_triggered=rule_code,
            decision=QADecision.QUERY,
            reviewer=None,
            note=f"Automated QA flag ({'hard stop' if is_hard_stop else 'soft flag'}).",
        )

    if triggered:
        submission.qa_status = QAStatus.QUERY
        submission.save(update_fields=["qa_status"])

    return triggered


def record_human_decision(
    *, submission: QUANSubmission, reviewer, decision: str, note: str, rule_code: str = ""
) -> QAEvent:
    """The only way qa_status ever reaches QA_PASSED -- always a human
    QAEvent.decision=ACCEPT, with a mandatory note either way
    (docs/15_QA_AND_DATA_QUALITY.md step 3-4)."""
    if not note.strip():
        raise ValueError("A note is required to record a QA decision.")

    event = QAEvent.objects.create(
        submission=submission, reviewer=reviewer, decision=decision, note=note, rule_triggered=rule_code
    )

    if decision == QADecision.ACCEPT:
        submission.qa_status = QAStatus.QA_PASSED
        # Completes the invitation token's own funnel tracking
        # (docs/10_INVITATION_AND_CONSENT.md) -- reconciliation already
        # advances it to SUBMITTED when the raw Kobo submission first
        # arrives; QA_PASSED is the one stage only a human decision can
        # reach.
        token = InvitationToken.objects.filter(sample_case=submission.sample_case).order_by("-issued_at").first()
        if token is not None:
            advance_token_status(token, TokenStatus.QA_PASSED)
    elif decision == QADecision.REJECT:
        submission.qa_status = QAStatus.REJECTED
    else:
        submission.qa_status = QAStatus.QUERY
    submission.save(update_fields=["qa_status"])

    log_action(
        "qa.decision",
        event,
        {
            "decision": decision,
            "submission_id": submission.id,
            "reviewer_id": getattr(reviewer, "id", None),
            "resulting_qa_status": submission.qa_status,
        },
    )
    return event
