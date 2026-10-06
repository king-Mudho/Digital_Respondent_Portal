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
    expired_invitations,
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
    ra = _user(Role.CONTACT_RA, "fu_api")
    other = APIClient()
    other.force_authenticate(_user(Role.CONTACT_RA, "fu_other"))
    main_case.assigned_ra = ra
    main_case.save(update_fields=["assigned_ra"])
    client = APIClient()
    client.force_authenticate(ra)

    # Another Contact RA's queue holds only its own cases, and it can't mark this one.
    assert other.get("/api/v1/follow-ups/").json()["results"] == []
    assert other.post("/api/v1/follow-ups/mark-sent/", {"sample_id": main_case.sample_id, "template": "drp_reminder_day2"}).status_code == 403

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


# --- A respondent who has booked a call is not chased (2026-10-06) ------------------------------------------------

def _appointment(case, status="REQUESTED", mode="PHONE"):
    from apps.contacts.models import Appointment

    return Appointment.objects.create(
        sample_case=case, scheduled_for=timezone.now() + timedelta(days=1), mode=mode, status=status,
    )


@pytest.mark.parametrize("status", ["REQUESTED", "CONFIRMED"])
def test_a_case_with_an_open_appointment_gets_no_reminder(main_case, status):
    _invited(main_case, days_ago=2)
    assert [f["sample_id"] for f in due_follow_ups()] == [main_case.sample_id]
    _appointment(main_case, status=status)
    assert due_follow_ups() == []


@pytest.mark.parametrize("status", ["COMPLETED", "MISSED", "CANCELLED"])
def test_reminders_resume_once_the_appointment_is_over(main_case, status):
    _invited(main_case, days_ago=2)
    _appointment(main_case, status=status)
    assert [f["sample_id"] for f in due_follow_ups()] == [main_case.sample_id]


def test_a_case_with_a_booked_call_never_becomes_nonresponse(main_case):
    # The worst case before the fix: both reminders marked sent, so the nightly rule replaced a respondent who had
    # consented and asked for a call.
    _invited(main_case, days_ago=8)
    ra = _user(Role.CONTACT_RA, "fu_ra_appt")
    record_manual_follow_up(sample_case=main_case, template_name="drp_reminder_day2", user=ra)
    record_manual_follow_up(sample_case=main_case, template_name="drp_reminder_day7_final", user=ra)
    _appointment(main_case, status="CONFIRMED")

    assert exhaust_nonresponse_cases() == []
    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S05_INVITATION_SENT


def test_appointment_status_changes_are_audited_with_who_and_from_what(main_case):
    appointment = _appointment(main_case)
    client = APIClient()
    client.force_authenticate(_user(Role.FIELD_COORDINATOR, "fu_fc_appt"))
    resp = client.post(f"/api/v1/appointments/{appointment.pk}/status/", {"status": "CONFIRMED"}, format="json")
    assert resp.status_code == 200
    event = AuditEvent.objects.get(action="appointment.status_changed")
    assert event.metadata["from"] == "REQUESTED" and event.metadata["to"] == "CONFIRMED"
    assert event.metadata["sample_id"] == main_case.sample_id and event.user.username == "fu_fc_appt"


# --- An invitation that has run out is re-issued, not reminded (2026-10-06) ---------------------------------------

def _expire(token, days_ago=1):
    token.expires_at = timezone.now() - timedelta(days=days_ago)
    token.save(update_fields=["expires_at"])


@pytest.fixture
def whatsapp_sent(monkeypatch):
    """A connected WhatsApp account that records what it would send."""
    from apps.messaging.whatsapp_client import WhatsAppClient

    sent = []
    monkeypatch.setattr(WhatsAppClient, "send_template_message",
                        lambda self, *, to_phone, template_name, params=None: sent.append((to_phone, template_name)) or {})
    return sent


def test_no_reminder_for_a_link_past_its_expiry_date(main_case, whatsapp_sent):
    token = _invited(main_case, days_ago=20)
    assert [f["sample_id"] for f in due_follow_ups()] == [main_case.sample_id]  # still live: the Day 7 reminder
    _expire(token)
    assert due_follow_ups() == []
    assert dispatch_due_reminders() == [] and whatsapp_sent == []


def test_a_live_link_is_still_reminded_automatically(main_case, whatsapp_sent):
    _invited(main_case, days_ago=2)
    assert len(dispatch_due_reminders()) == 1
    assert whatsapp_sent == [("263771234567", "drp_reminder_day2")]


def test_an_expired_invitation_is_listed_to_re_invite(main_case):
    token = _invited(main_case, days_ago=20)
    assert expired_invitations() == []
    _expire(token, days_ago=2)
    [item] = expired_invitations()
    assert (item["sample_id"], item["reason"], item["respondent_name"]) == (main_case.sample_id, "expired", "Jane Doe")
    assert item["expired_on"] == timezone.localdate() - timedelta(days=2)


def test_a_case_left_with_no_live_invitation_is_listed(main_case):
    # SID-2026-000202 on production: its invitation was revoked, so it dropped off every list while reading S05.
    from apps.invitations.services import revoke_token

    revoke_token(_invited(main_case, days_ago=3), "Wrong contact")
    [item] = expired_invitations()
    assert (item["sample_id"], item["reason"], item["invited_on"]) == (main_case.sample_id, "no_live_invitation", None)


def test_a_new_invitation_takes_the_case_off_the_expired_list(main_case):
    _expire(_invited(main_case, days_ago=20))
    issue_invitation(main_case)
    assert expired_invitations() == []
    assert [f["sample_id"] for f in due_follow_ups()] == []  # a fresh link: no reminder due on day 0


def test_a_prepared_case_with_no_invitation_yet_is_not_expired(main_case):
    for status in ("S01", "S02", "S03", "S04"):
        transition_workflow_status(main_case, status)
    assert expired_invitations() == []


@pytest.mark.django_db
def test_the_follow_ups_endpoint_lists_expired_invitations_by_ra(main_case):
    _expire(_invited(main_case, days_ago=20))
    ra = _user(Role.CONTACT_RA, "fu_exp_ra")
    main_case.assigned_ra = ra
    main_case.save(update_fields=["assigned_ra"])
    mine, other = APIClient(), APIClient()
    mine.force_authenticate(ra)
    other.force_authenticate(_user(Role.CONTACT_RA, "fu_exp_other"))
    assert [e["sample_id"] for e in mine.get("/api/v1/follow-ups/").json()["expired"]] == [main_case.sample_id]
    assert other.get("/api/v1/follow-ups/").json()["expired"] == []


# --- WhatsApp only to a mobile (2026-10-06) ----------------------------------------------------------------------

def test_a_landline_gets_no_whatsapp_link_and_no_automatic_reminder(main_case, whatsapp_sent):
    _invited(main_case, days_ago=2, phone="+263 9 75315")
    [item] = due_follow_ups()
    assert item["phone"] == "+263 9 75315" and item["can_whatsapp"] is False
    assert item["whatsapp_link"].startswith("https://wa.me/?text=")  # choose the contact; never the landline
    assert dispatch_due_reminders() == [] and whatsapp_sent == []


def test_the_mobile_is_found_in_either_field(main_case):
    _invited(main_case, days_ago=2, phone="0242 700000")
    Respondent.objects.filter(sample_case=main_case).update(phone="0773 248 965")
    [item] = due_follow_ups()
    assert item["can_whatsapp"] is True and item["whatsapp_link"].startswith("https://wa.me/263773248965?")
