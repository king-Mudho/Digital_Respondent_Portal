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
from apps.sampling.services import advance_case_on_qa_outcome

from .models import ExceptionStatus, QADecision, QAEvent, QARuleThreshold

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
        advance_case_on_qa_outcome(submission.sample_case, passed=False)

    return triggered


class InvalidExceptionTransition(ValueError):
    """Raised when an exception is moved to a state that makes no sense."""


def open_exceptions(assigned_to=None, include_resolved: bool = False):
    """The daily exception queue (ResearchOS brief A6).

    Automated flags only -- `reviewer__isnull=True`. A human decision row is
    terminal by nature and is not something anyone needs to own.
    """
    qs = (
        QAEvent.objects.filter(reviewer__isnull=True)
        .select_related("submission__sample_case", "kii_record", "document_record", "assigned_to")
        .order_by("created_at")  # oldest first: the queue is a backlog
    )
    if not include_resolved:
        qs = qs.filter(status__in=[ExceptionStatus.OPEN, ExceptionStatus.IN_PROGRESS])
    if assigned_to is not None:
        qs = qs.filter(assigned_to=assigned_to)
    return qs


def assign_exception(event: QAEvent, *, assignee, changed_by) -> QAEvent:
    """Give an exception an owner. Assigning to None releases it."""
    if not event.is_automated_flag:
        raise InvalidExceptionTransition(
            "Only an automated QA flag can be assigned; this row is a recorded human decision."
        )
    if event.status in (ExceptionStatus.RESOLVED, ExceptionStatus.DISMISSED):
        raise InvalidExceptionTransition(f"This exception is already {event.status.lower()}.")

    event.assigned_to = assignee
    # Picking something up is what moves it off the open pile -- there is no
    # separate "start work" click to forget.
    event.status = ExceptionStatus.IN_PROGRESS if assignee is not None else ExceptionStatus.OPEN
    event.save(update_fields=["assigned_to", "status"])

    log_action(
        "qa.exception_assigned",
        event,
        {
            "rule": event.rule_triggered,
            "assigned_to_id": getattr(assignee, "id", None),
            "changed_by_id": getattr(changed_by, "id", None),
        },
    )
    return event


def resolve_exception(event: QAEvent, *, status: str, note: str, resolved_by) -> QAEvent:
    """Close an exception as resolved or dismissed. A note is mandatory for
    the same reason it is on a QA decision: a closure nobody explained is
    indistinguishable from one nobody looked at."""
    if not event.is_automated_flag:
        raise InvalidExceptionTransition(
            "Only an automated QA flag can be resolved; this row is a recorded human decision."
        )
    if status not in (ExceptionStatus.RESOLVED, ExceptionStatus.DISMISSED):
        raise InvalidExceptionTransition("An exception closes as RESOLVED or DISMISSED.")
    if not note.strip():
        raise InvalidExceptionTransition("A note is required to close a QA exception.")

    event.status = status
    event.resolution_note = note.strip()
    event.resolved_by = resolved_by
    event.resolved_at = timezone.now()
    event.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])

    log_action(
        "qa.exception_resolved",
        event,
        {
            "rule": event.rule_triggered,
            "status": status,
            "resolved_by_id": getattr(resolved_by, "id", None),
        },
    )
    return event


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
    if decision == QADecision.ACCEPT:
        advance_case_on_qa_outcome(submission.sample_case, passed=True)
    elif decision == QADecision.QUERY:
        advance_case_on_qa_outcome(submission.sample_case, passed=False)

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
