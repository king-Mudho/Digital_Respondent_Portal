"""
QA exception ownership (ResearchOS brief A6: "daily exception queue with
owner/status").

Before this, a triggered rule created a QAEvent and nothing else -- no
owner, no status, no resolution. The queue was a list rather than a
workflow, so an exception could not be assigned, tracked, or shown to have
been dealt with. docs/28's "daily QA exceptions are visible, assigned and
resolvable" was unmeetable.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.kobo.models import QAStatus, QUANSubmission
from apps.qa.models import ExceptionStatus, QADecision, QAEvent
from apps.qa.services import (
    InvalidExceptionTransition,
    assign_exception,
    open_exceptions,
    resolve_exception,
)


@pytest.fixture
def qa_user(db):
    role, _ = Role.objects.get_or_create(name=Role.QUAN_QA_RA)
    return User.objects.create_user(username="qa_owner", password="testpass123", role=role)


@pytest.fixture
def qa_client(qa_user):
    client = APIClient()
    client.force_authenticate(user=qa_user)
    return client


@pytest.fixture
def submission(main_case):
    from django.utils import timezone

    return QUANSubmission.objects.create(
        sample_case=main_case, kobo_submission_uuid="uuid-exc-1",
        administration_mode="01", submitted_at=timezone.now(), qa_status=QAStatus.QUERY,
    )


@pytest.fixture
def flag(submission):
    """An automated flag -- reviewer is None, which is what makes it an
    exception rather than a recorded human decision."""
    return QAEvent.objects.create(
        submission=submission, rule_triggered="min_plausible_duration_seconds",
        decision=QADecision.QUERY, reviewer=None, note="Automated QA flag (soft flag).",
    )


# --- defaults ------------------------------------------------------------

def test_a_new_flag_starts_open_and_unowned(flag):
    assert flag.status == ExceptionStatus.OPEN
    assert flag.assigned_to is None
    assert flag.is_automated_flag is True


def test_a_human_decision_is_not_an_exception(submission, qa_user):
    decision = QAEvent.objects.create(
        submission=submission, decision=QADecision.ACCEPT, reviewer=qa_user, note="Looks fine.",
    )

    assert decision.is_automated_flag is False
    assert decision not in list(open_exceptions())


# --- assignment ----------------------------------------------------------

def test_assigning_takes_it_off_the_open_pile(flag, qa_user):
    assign_exception(flag, assignee=qa_user, changed_by=qa_user)

    flag.refresh_from_db()
    assert flag.assigned_to == qa_user
    assert flag.status == ExceptionStatus.IN_PROGRESS
    assert AuditEvent.objects.filter(action="qa.exception_assigned").exists()


def test_releasing_returns_it_to_open(flag, qa_user):
    assign_exception(flag, assignee=qa_user, changed_by=qa_user)

    assign_exception(flag, assignee=None, changed_by=qa_user)

    flag.refresh_from_db()
    assert flag.assigned_to is None
    assert flag.status == ExceptionStatus.OPEN


def test_a_human_decision_cannot_be_assigned(submission, qa_user):
    decision = QAEvent.objects.create(
        submission=submission, decision=QADecision.ACCEPT, reviewer=qa_user, note="Fine.",
    )

    with pytest.raises(InvalidExceptionTransition, match="automated QA flag"):
        assign_exception(decision, assignee=qa_user, changed_by=qa_user)


def test_a_closed_exception_cannot_be_reassigned(flag, qa_user):
    resolve_exception(flag, status=ExceptionStatus.RESOLVED, note="Fixed.", resolved_by=qa_user)

    with pytest.raises(InvalidExceptionTransition, match="already"):
        assign_exception(flag, assignee=qa_user, changed_by=qa_user)


# --- resolution ----------------------------------------------------------

def test_resolving_records_who_when_and_why(flag, qa_user):
    resolve_exception(flag, status=ExceptionStatus.RESOLVED, note="Duration confirmed with the RA.", resolved_by=qa_user)

    flag.refresh_from_db()
    assert flag.status == ExceptionStatus.RESOLVED
    assert flag.resolved_by == qa_user
    assert flag.resolved_at is not None
    assert "confirmed with the RA" in flag.resolution_note
    assert AuditEvent.objects.filter(action="qa.exception_resolved").exists()


def test_closing_without_a_note_is_refused(flag, qa_user):
    """Same reason a QA decision needs one: a closure nobody explained is
    indistinguishable from one nobody looked at."""
    with pytest.raises(InvalidExceptionTransition, match="note is required"):
        resolve_exception(flag, status=ExceptionStatus.RESOLVED, note="   ", resolved_by=qa_user)

    flag.refresh_from_db()
    assert flag.status == ExceptionStatus.OPEN


def test_only_resolved_or_dismissed_close_an_exception(flag, qa_user):
    with pytest.raises(InvalidExceptionTransition):
        resolve_exception(flag, status=ExceptionStatus.IN_PROGRESS, note="n/a", resolved_by=qa_user)


# --- the queue -----------------------------------------------------------

def test_queue_hides_closed_exceptions_by_default(flag, qa_user):
    assert flag in list(open_exceptions())

    resolve_exception(flag, status=ExceptionStatus.DISMISSED, note="Not a real problem.", resolved_by=qa_user)

    assert flag not in list(open_exceptions())
    assert flag in list(open_exceptions(include_resolved=True))


def test_queue_is_oldest_first(submission):
    """It is a backlog, not a feed -- the oldest unresolved exception is the
    one most at risk of being forgotten."""
    first = QAEvent.objects.create(submission=submission, rule_triggered="a", decision=QADecision.QUERY, reviewer=None)
    second = QAEvent.objects.create(submission=submission, rule_triggered="b", decision=QADecision.QUERY, reviewer=None)

    assert list(open_exceptions())[:2] == [first, second]


def test_mine_filter(flag, qa_user, db):
    other_role, _ = Role.objects.get_or_create(name=Role.FIELD_COORDINATOR)
    other = User.objects.create_user(username="qa_other", password="x", role=other_role)
    assign_exception(flag, assignee=other, changed_by=other)

    assert flag not in list(open_exceptions(assigned_to=qa_user))
    assert flag in list(open_exceptions(assigned_to=other))


# --- the API -------------------------------------------------------------

def test_api_lists_with_context_to_act_on(qa_client, flag, main_case):
    body = qa_client.get("/api/v1/qa/exceptions/").json()

    row = body["results"][0] if isinstance(body, dict) else body[0]
    assert row["rule_triggered"] == "min_plausible_duration_seconds"
    assert row["subject_type"] == "QUAN submission"
    assert row["subject_ref"] == main_case.sample_id
    assert row["status"] == ExceptionStatus.OPEN
    assert "age_days" in row


def test_api_assign_and_resolve(qa_client, flag, qa_user):
    a = qa_client.post(f"/api/v1/qa/exceptions/{flag.id}/assign/", {"assigned_to": qa_user.id}, format="json")
    assert a.status_code == 200
    assert a.json()["assigned_to_username"] == "qa_owner"
    assert a.json()["status"] == ExceptionStatus.IN_PROGRESS

    r = qa_client.post(
        f"/api/v1/qa/exceptions/{flag.id}/resolve/",
        {"status": "RESOLVED", "note": "Checked against the RA's log."}, format="json",
    )
    assert r.status_code == 200
    assert r.json()["status"] == ExceptionStatus.RESOLVED
    assert r.json()["resolved_by_username"] == "qa_owner"


def test_api_refuses_a_closure_without_a_note(qa_client, flag):
    resp = qa_client.post(f"/api/v1/qa/exceptions/{flag.id}/resolve/", {"status": "RESOLVED", "note": ""}, format="json")

    assert resp.status_code == 400
    flag.refresh_from_db()
    assert flag.status == ExceptionStatus.OPEN


def test_a_kii_ra_cannot_touch_the_qa_exception_queue(db, flag):
    role, _ = Role.objects.get_or_create(name=Role.KII_RA)
    user = User.objects.create_user(username="exc_kii_ra", password="x", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.get("/api/v1/qa/exceptions/").status_code == 403
    assert client.post(f"/api/v1/qa/exceptions/{flag.id}/assign/", {}, format="json").status_code == 403
