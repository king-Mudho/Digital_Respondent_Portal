"""
Reminder sequence (docs/12_CONTACT_CRM_AND_MESSAGING.md) and the S13
Nonresponse rule (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).

Rewritten 2026-09-14. The earlier tests asserted that, with no WhatsApp
account, a due reminder was written as a FAILED MessageLog, and that a case
became Nonresponse on day 8 by the calendar alone. Both were the defect:
the FAILED rows appeared on no screen, so no reminder could ever reach a
respondent, and a case could be replaced by a reserve with nobody having
followed up.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.services import issue_invitation
from apps.messaging.models import MessageLog, MessageStatus
from apps.messaging.services import (
    dispatch_due_reminders,
    due_follow_ups,
    exhaust_nonresponse_cases,
    record_manual_follow_up,
    whatsapp_digits,
)
from apps.sampling.models import WorkflowStatus
from apps.sampling.services import transition_workflow_status


def _invited(case, days_ago, *, phone="0771234567"):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    if phone is not None:
        Respondent.objects.create(
            sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
            is_eligible=True, whatsapp_number=phone,
        )
    issue_invitation(case)
    token = case.invitation_tokens.order_by("-issued_at").first()
    token.issued_at = timezone.now() - timedelta(days=days_ago)
    token.save(update_fields=["issued_at"])
    return token


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


# --- workflow on invitation (unchanged behaviour) ---------------------------

def test_issuing_invitation_advances_workflow_to_invitation_sent(main_case):
    _invited(main_case, days_ago=0)
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S05_INVITATION_SENT


def test_resend_does_not_regress_a_further_along_case(main_case):
    _invited(main_case, days_ago=0)
    transition_workflow_status(main_case, WorkflowStatus.S06_INVITATION_OPENED)
    transition_workflow_status(main_case, WorkflowStatus.S07_SURVEY_STARTED)

    issue_invitation(main_case, invitation_wave=2)

    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S07_SURVEY_STARTED


# --- automated dispatch -----------------------------------------------------

@pytest.mark.django_db
def test_without_whatsapp_nothing_is_sent_or_logged_and_the_reminder_waits_on_follow_ups(main_case):
    _invited(main_case, days_ago=2)

    assert dispatch_due_reminders() == []
    assert MessageLog.objects.count() == 0
    [item] = due_follow_ups()
    assert (item["sample_id"], item["template"]) == (main_case.sample_id, "drp_reminder_day2")


def test_no_reminder_before_its_day_offset(main_case):
    _invited(main_case, days_ago=1)
    assert due_follow_ups() == []


def test_a_missed_day_does_not_lose_the_reminder(main_case):
    """The old check was an exact day match: a reminder not handled on day
    2 was never offered again."""
    _invited(main_case, days_ago=4)
    [item] = due_follow_ups()
    assert item["template"] == "drp_reminder_day2"


def test_only_the_latest_due_reminder_is_offered(main_case):
    _invited(main_case, days_ago=9)
    [item] = due_follow_ups()
    assert item["template"] == "drp_reminder_day7_final"


def test_a_reminder_sent_by_hand_leaves_the_queue_and_is_attributed(main_case):
    _invited(main_case, days_ago=2)
    ra = _user(Role.CONTACT_RA, "fu_ra")

    record_manual_follow_up(sample_case=main_case, template_name="drp_reminder_day2", user=ra)

    assert due_follow_ups() == []
    log = MessageLog.objects.get()
    assert (log.status, log.triggered_by) == (MessageStatus.SENT, ra)
    assert AuditEvent.objects.filter(action="messaging.follow_up_sent").exists()


def test_cases_that_have_responded_are_not_chased(main_case):
    _invited(main_case, days_ago=3)
    transition_workflow_status(main_case, WorkflowStatus.S06_INVITATION_OPENED)
    transition_workflow_status(main_case, WorkflowStatus.S07_SURVEY_STARTED)
    assert due_follow_ups() == []


# --- S13 Nonresponse ---------------------------------------------------------

def test_nonresponse_requires_every_reminder_to_have_been_sent(main_case):
    _invited(main_case, days_ago=8)

    assert exhaust_nonresponse_cases() == []
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S05_INVITATION_SENT


def test_nonresponse_after_the_full_sequence_was_sent(main_case):
    _invited(main_case, days_ago=8)
    ra = _user(Role.CONTACT_RA, "fu_ra2")
    record_manual_follow_up(sample_case=main_case, template_name="drp_reminder_day2", user=ra)
    record_manual_follow_up(sample_case=main_case, template_name="drp_reminder_day7_final", user=ra)

    assert main_case in exhaust_nonresponse_cases()
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S13_NONRESPONSE


def test_reminders_for_an_earlier_invitation_do_not_count_for_a_resend(main_case):
    token = _invited(main_case, days_ago=20)
    ra = _user(Role.CONTACT_RA, "fu_ra3")
    for name in ("drp_reminder_day2", "drp_reminder_day7_final"):
        record_manual_follow_up(sample_case=main_case, template_name=name, user=ra)
    MessageLog.objects.update(created_at=token.issued_at + timedelta(days=3))

    resend = issue_invitation(main_case, invitation_wave=2)[2]
    resend.issued_at = timezone.now() - timedelta(days=9)
    resend.save(update_fields=["issued_at"])

    assert exhaust_nonresponse_cases() == []


def test_nonresponse_leaves_cases_within_the_sequence_window(main_case):
    _invited(main_case, days_ago=3)
    assert exhaust_nonresponse_cases() == []


# --- WhatsApp click-to-chat -------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("0771 234 567", "263771234567"),
    ("+263 77 123 4567", "263771234567"),
    ("00263771234567", "263771234567"),
    ("", ""),
])
def test_whatsapp_numbers_are_normalised_for_wa_me(raw, expected):
    assert whatsapp_digits(raw) == expected


# --- API ---------------------------------------------------------------------

@pytest.mark.django_db
def test_follow_up_endpoints_for_a_contact_ra(main_case):
    _invited(main_case, days_ago=2)
    client = APIClient()
    client.force_authenticate(_user(Role.CONTACT_RA, "fu_api"))

    [item] = client.get("/api/v1/follow-ups/").json()["results"]
    assert item["whatsapp_link"].startswith("https://wa.me/263771234567?text=Hello")

    resp = client.post("/api/v1/follow-ups/mark-sent/", {"sample_id": main_case.sample_id, "template": item["template"]})
    assert resp.status_code == 201
    assert client.get("/api/v1/follow-ups/").json()["results"] == []


@pytest.mark.django_db
def test_follow_up_permissions(main_case):
    _invited(main_case, days_ago=2)
    supervisor = APIClient()
    supervisor.force_authenticate(_user(Role.SUPERVISOR_READONLY, "fu_sup"))
    kii = APIClient()
    kii.force_authenticate(_user(Role.KII_RA, "fu_kii"))
    body = {"sample_id": main_case.sample_id, "template": "drp_reminder_day2"}

    assert supervisor.get("/api/v1/follow-ups/").status_code == 200
    assert supervisor.post("/api/v1/follow-ups/mark-sent/", body).status_code == 403
    assert kii.get("/api/v1/follow-ups/").status_code == 403
    assert kii.post("/api/v1/follow-ups/mark-sent/", body).status_code == 403


def test_a_revoked_invitation_does_not_start_the_reminder_clock(main_case):
    from apps.invitations.services import revoke_token

    token = _invited(main_case, days_ago=3)
    revoke_token(token, "Wrong contact")
    assert due_follow_ups() == []
