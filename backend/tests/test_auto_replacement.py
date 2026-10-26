"""Automatic Reserve replacement (apps/sampling/replacement.py, PI decision 2026-10-12). Twilio is a fake requests.post.
Under test:

- nothing is activated while the policy is off, or for an outcome the PI did not tick, or beyond the daily limit;
- each outcome activates the Main case's own paired Reserve, with its authorised reason, the PI who switched the policy
  on as authoriser, an evidence note, and an audit entry marked automatic (AGENTS.md rule 4);
- an already-activated Reserve or a Main case with no pair is never touched; the replaced Main keeps its outcome and
  loses its open link; "no reply to the introduction" moves the Main to S13 first; running twice changes nothing;
- the Reserve is introduced on WhatsApp, tried again next morning if it could not be, listed when it has no mobile,
  and a YES sends its link while a NO starts no further replacement;
- activated Reserves now reach batches and introductions, and locked ones still never do;
- only the PI changes the policy, and every change is audited.
"""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation
from apps.messaging import outreach, tasks
from apps.messaging import twilio_client as tw
from apps.messaging.models import Outreach, OutreachStatus
from apps.sampling.models import ReplacementPolicy, ReserveStatus, SampleCase, SampleType
from apps.sampling.replacement import run_auto_replacement
from apps.sampling.services import (
    activate_reserve,
    contactable_cases,
    create_sample_case,
    transition_workflow_status,
)

URL = "/api/v1/reserve-replacement/"
ALL = ["REFUSED", "NONRESPONSE", "NO_REPLY", "INELIGIBLE", "DUPLICATE_INACTIVE"]


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    settings.TWILIO_WA_CONTENT_INTRO, settings.TWILIO_WA_CONTENT_INTRO_REMINDER = "HXintro", "HXintroReminder"
    settings.TWILIO_WA_CONTENT_INVITATION = "HXinv"
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued"}))

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(tasks.handle_inbound_message, "delay", lambda *args: outreach.handle_inbound(*args))
    return sent


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj, first_name="Happyson", last_name="Saina")


@pytest.fixture
def pi(db):
    return _user(Role.PI_ADMIN, "rep_pi")


def _switch_on(pi, triggers=ALL, daily_max=20):
    policy = ReplacementPolicy.current()
    policy.enabled, policy.triggers, policy.daily_max = True, list(triggers), daily_max
    policy.enabled_by, policy.enabled_at = pi, timezone.now()
    policy.save()
    return policy


def _person(case, phone="0771234567"):
    return Respondent.objects.create(sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD,
                                     is_eligible=True, phone=phone)


def _to(case, *statuses):
    for status in statuses:
        transition_workflow_status(case, status)
    case.refresh_from_db()
    return case


def _pair(organisation, stratum, *, phone="0772222222"):
    """A further Main case with its own locked Reserve (which has a mobile on record)."""
    main = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    reserve = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.RESERVE, year=2026)
    main.matched_case = reserve
    main.save(update_fields=["matched_case"])
    if phone:
        _person(reserve, phone)
    return main, reserve


@pytest.fixture
def refused(main_case, locked_reserve_case):
    _person(locked_reserve_case, "0779999999")
    return _to(main_case, "S01", "S02", "S03", "S12")


# --- The policy decides ----------------------------------------------------------------------------------------------

def test_nothing_is_activated_while_the_policy_is_off(twilio, pi, refused, locked_reserve_case):
    assert run_auto_replacement() == {"skipped": "automatic replacement is off"}
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.LOCKED


def test_only_the_outcomes_the_pi_ticked_are_replaced(twilio, pi, refused, locked_reserve_case):
    _switch_on(pi, triggers=["NONRESPONSE"])
    assert run_auto_replacement()["activated"] == []
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.LOCKED


def test_the_daily_limit_holds(twilio, pi, organisation, stratum):
    pairs = [_pair(organisation, stratum, phone=f"07722222{n:02d}") for n in range(3)]
    for main, _ in pairs:
        _to(main, "S01", "S02", "S03", "S12")
    _switch_on(pi, daily_max=2)
    assert len(run_auto_replacement()["activated"]) == 2
    assert len(run_auto_replacement()["activated"]) == 0  # the limit is per day, not per run
    assert SampleCase.objects.filter(sample_type="RESERVE", status="ACTIVATED").count() == 2


# --- Activation ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path,trigger,reason", [
    (("S01", "S02", "S03", "S12"), "REFUSED", "REFUSAL"),
    (("S01", "S02", "S14"), "INELIGIBLE", "INELIGIBLE"),
    (("S01", "S15"), "DUPLICATE_INACTIVE", "INACTIVE"),
])
def test_each_outcome_activates_the_paired_reserve_under_its_reason(twilio, pi, main_case, locked_reserve_case, path, trigger, reason):
    _person(locked_reserve_case, "0779999999")
    _to(main_case, *path)
    _switch_on(pi, triggers=[trigger])
    assert run_auto_replacement()["activated"] == [f"{main_case.sample_id}->{locked_reserve_case.sample_id}"]
    locked_reserve_case.refresh_from_db()
    assert (locked_reserve_case.status, locked_reserve_case.activation_reason, locked_reserve_case.activated_by) == (
        ReserveStatus.ACTIVATED, reason, pi)
    assert main_case.sample_id in locked_reserve_case.activation_evidence_note
    assert "standing authorisation Happyson Saina" in locked_reserve_case.activation_evidence_note
    event = AuditEvent.objects.get(action="reserve.activated")
    assert event.metadata["automatic"] is True and event.metadata["replaces"] == main_case.sample_id


def test_nonresponse_exhausted_is_replaced(twilio, pi, main_case, locked_reserve_case):
    _person(locked_reserve_case, "0779999999")
    _person(main_case)
    _to(main_case, "S01", "S02", "S03")
    issue_invitation(main_case, channel="WHATSAPP", issued_by=pi)
    _to(main_case, "S13")
    _switch_on(pi, triggers=["NONRESPONSE"])
    run_auto_replacement()
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.activation_reason == "NONRESPONSE_EXHAUSTED"
    # The Main case's open link is revoked (no 401st respondent), and it keeps its outcome.
    assert InvitationToken.objects.get(sample_case=main_case).status == TokenStatus.REVOKED
    main_case.refresh_from_db()
    assert main_case.workflow_status == "S13"


def test_no_reply_to_the_introduction_moves_the_main_to_s13_and_replaces_it(twilio, pi, main_case, locked_reserve_case):
    _person(locked_reserve_case, "0779999999")
    _person(main_case)
    _to(main_case, "S01", "S02", "S03")
    Outreach.objects.create(sample_case=main_case, channel="WHATSAPP", number_hash="h", number_masked="m",
                            intro_sent_at=timezone.now() - timedelta(days=8), status=OutreachStatus.NO_REPLY)
    _switch_on(pi, triggers=["NO_REPLY"])
    run_auto_replacement()
    main_case.refresh_from_db()
    locked_reserve_case.refresh_from_db()
    assert main_case.workflow_status == "S13" and locked_reserve_case.status == ReserveStatus.ACTIVATED
    assert "did not reply to the introduction" in locked_reserve_case.activation_evidence_note


@pytest.mark.parametrize("appointment, replaced", [("REQUESTED", False), ("CONFIRMED", False), ("MISSED", True), ("CANCELLED", True)])
@pytest.mark.parametrize("trigger", ["NO_REPLY", "NONRESPONSE"])
def test_a_case_that_asked_for_a_call_is_never_replaced_while_the_call_is_open(twilio, pi, main_case, locked_reserve_case,
                                                                              trigger, appointment, replaced):
    """2026-10-26: SID-2026-000158 asked on 6 Oct for a WhatsApp voice interview, and on 24 Oct automatic replacement
    closed it as Nonresponse for not answering the introduction. A respondent who asked for a call has responded."""
    from apps.contacts.models import Appointment

    _person(locked_reserve_case, "0779999999")
    _person(main_case)
    _to(main_case, "S01", "S02", "S03")
    if trigger == "NO_REPLY":
        Outreach.objects.create(sample_case=main_case, channel="WHATSAPP", number_hash="h", number_masked="m",
                                intro_sent_at=timezone.now() - timedelta(days=8), status=OutreachStatus.NO_REPLY)
    else:
        issue_invitation(main_case, channel="WHATSAPP", issued_by=pi)
        _to(main_case, "S13")
    Appointment.objects.create(sample_case=main_case, scheduled_for=timezone.now() - timedelta(days=5), mode="PHONE", status=appointment)
    _switch_on(pi, triggers=[trigger])
    run_auto_replacement()
    locked_reserve_case.refresh_from_db()
    main_case.refresh_from_db()
    assert (locked_reserve_case.status == ReserveStatus.ACTIVATED) is replaced
    if not replaced:
        assert main_case.workflow_status == ("S03" if trigger == "NO_REPLY" else "S13")  # untouched


def test_a_refusal_is_still_replaced_even_with_a_call_booked(twilio, pi, refused, locked_reserve_case):
    from apps.contacts.models import Appointment

    Appointment.objects.create(sample_case=refused, scheduled_for=timezone.now(), mode="PHONE", status="REQUESTED")
    _switch_on(pi, triggers=["REFUSED"])
    run_auto_replacement()
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.status == ReserveStatus.ACTIVATED  # a refusal is an outcome of its own


def test_an_introduction_still_waiting_for_a_reply_is_not_replaced(twilio, pi, main_case, locked_reserve_case):
    _person(main_case)
    _to(main_case, "S01", "S02", "S03")
    Outreach.objects.create(sample_case=main_case, channel="WHATSAPP", number_hash="h", number_masked="m",
                            intro_sent_at=timezone.now(), status=OutreachStatus.REMINDED)
    _switch_on(pi)
    assert run_auto_replacement()["activated"] == []


def test_a_main_without_a_pair_or_with_its_reserve_already_active_is_left_alone(twilio, pi, refused, locked_reserve_case, organisation, stratum):
    activate_reserve(locked_reserve_case, reason="REFUSAL", activated_by=pi, evidence_note="by hand")
    lonely = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    _to(lonely, "S01", "S02", "S03", "S12")
    _switch_on(pi)
    assert run_auto_replacement()["activated"] == []
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.activation_evidence_note == "by hand"  # the earlier activation is untouched


def test_running_twice_changes_nothing(twilio, pi, refused, locked_reserve_case):
    _switch_on(pi)
    run_auto_replacement()
    assert run_auto_replacement()["activated"] == []
    assert AuditEvent.objects.filter(action="reserve.activated").count() == 1
    assert Outreach.objects.filter(sample_case=locked_reserve_case).count() == 1


def test_the_reserve_goes_to_the_main_cases_contact_ra(twilio, pi, refused, main_case, locked_reserve_case):
    ra = _user(Role.CONTACT_RA, "rep_ra")
    SampleCase.objects.filter(pk=main_case.pk).update(assigned_ra=ra)
    _switch_on(pi)
    run_auto_replacement()
    locked_reserve_case.refresh_from_db()
    assert locked_reserve_case.assigned_ra == ra


# --- Contacting the Reserve ------------------------------------------------------------------------------------------

def test_the_activated_reserve_is_introduced_on_whatsapp(twilio, pi, refused, locked_reserve_case):
    _switch_on(pi)
    assert run_auto_replacement()["introduced"] == 1
    assert twilio[-1]["ContentSid"] == "HXintro" and twilio[-1]["To"] == "whatsapp:+263779999999"
    assert Outreach.objects.get(sample_case=locked_reserve_case).status == OutreachStatus.INTRO_SENT


def test_an_introduction_that_could_not_go_is_tried_again_next_morning(twilio, pi, refused, locked_reserve_case, settings):
    settings.TWILIO_WHATSAPP_FROM = ""  # WhatsApp not set up on the first morning
    _switch_on(pi)
    first = run_auto_replacement()
    locked_reserve_case.refresh_from_db()
    assert first["introduced"] == 0 and locked_reserve_case.status == ReserveStatus.ACTIVATED
    assert locked_reserve_case.metadata["auto_replacement"]["contact_note"]
    settings.TWILIO_WHATSAPP_FROM = "+15550001111"
    assert run_auto_replacement()["introduced"] == 1


def test_a_reserve_with_no_mobile_is_listed_as_needing_contact_details(twilio, pi, main_case, locked_reserve_case):
    _to(main_case, "S01", "S02", "S03", "S12")
    _switch_on(pi)
    run_auto_replacement()
    rows = _client(pi).get(URL).json()["replacements"]
    assert [(r["reserve"], r["state"]) for r in rows] == [(locked_reserve_case.sample_id, "NEEDS_CONTACT")]


def test_a_yes_from_the_reserve_sends_its_link_and_a_no_starts_nothing_more(twilio, pi, refused, locked_reserve_case, organisation, stratum):
    from tests.test_outreach import _reply

    _switch_on(pi)
    run_auto_replacement()
    assert _reply("YES", number="263779999999").status_code == 200
    token = InvitationToken.objects.get(sample_case=locked_reserve_case)
    assert Outreach.objects.get(sample_case=locked_reserve_case).status == OutreachStatus.ACCEPTED and token.status != "REVOKED"
    # A second pair whose Reserve says no: recorded, and nothing else is activated for it.
    main2, reserve2 = _pair(organisation, stratum, phone="0773333333")
    _to(main2, "S01", "S02", "S03", "S12")
    run_auto_replacement()
    _reply("NO", number="263773333333")
    assert Outreach.objects.get(sample_case=reserve2).status == OutreachStatus.DECLINED
    activated_before = SampleCase.objects.filter(status="ACTIVATED").count()
    run_auto_replacement()
    assert SampleCase.objects.filter(status="ACTIVATED").count() == activated_before
    assert not contactable_cases().filter(pk=reserve2.pk).exists()


# --- Reserves and contact paths (rule 4) -----------------------------------------------------------------------------

def test_activated_reserves_reach_batches_and_introductions_and_locked_ones_never_do(twilio, pi, main_case, locked_reserve_case):
    from apps.invitations.batch import batch_candidates

    _person(locked_reserve_case, "0779999999")
    assert not batch_candidates(("WHATSAPP",)).filter(pk=locked_reserve_case.pk).exists()
    assert not outreach.introduction_candidates().filter(pk=locked_reserve_case.pk).exists()
    with pytest.raises(outreach.OutreachError):
        outreach.send_introduction(locked_reserve_case, user=pi)
    activate_reserve(locked_reserve_case, reason="REFUSAL", activated_by=pi, evidence_note="x")
    assert batch_candidates(("WHATSAPP",)).filter(pk=locked_reserve_case.pk).exists()
    assert outreach.introduction_candidates().filter(pk=locked_reserve_case.pk).exists()
    _, _, token = issue_invitation(locked_reserve_case, channel="WHATSAPP", issued_by=pi)  # once invited, it leaves
    assert not batch_candidates(("WHATSAPP",)).filter(pk=locked_reserve_case.pk).exists()
    # ...and stays out once that link is no longer open: a Reserve has no S05+ status to keep it out the way a Main has.
    InvitationToken.objects.filter(pk=token.pk).update(status=TokenStatus.SUBMITTED)
    assert not batch_candidates(("WHATSAPP",)).filter(pk=locked_reserve_case.pk).exists()
    assert not outreach.introduction_candidates().filter(pk=locked_reserve_case.pk).exists()


# --- Who changes the policy ------------------------------------------------------------------------------------------

def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_only_the_pi_changes_the_policy_and_every_change_is_audited(pi):
    body = {"enabled": True, "triggers": ["REFUSED"], "daily_max": 10}
    for role in (Role.FIELD_COORDINATOR, Role.SUPERVISOR_READONLY, Role.CONTACT_RA):
        assert _client(_user(role, f"rep_{role.lower()}")).put(URL, body, format="json").status_code == 403
    assert ReplacementPolicy.current().enabled is False
    resp = _client(pi).put(URL, body, format="json")
    assert resp.status_code == 200 and resp.json()["policy"]["enabled_by"] == "Happyson Saina"
    policy = ReplacementPolicy.current()
    assert (policy.enabled, policy.triggers, policy.enabled_by) == (True, ["REFUSED"], pi)
    assert AuditEvent.objects.get(action="reserve.auto_policy_changed").metadata["after"]["enabled"] is True
    assert _client(_user(Role.SUPERVISOR_READONLY, "rep_sup2")).get(URL).status_code == 200
    assert _client(_user(Role.CONTACT_RA, "rep_ra2")).get(URL).status_code == 403


def test_it_cannot_be_switched_on_with_nothing_ticked(pi):
    resp = _client(pi).put(URL, {"enabled": True, "triggers": [], "daily_max": 10}, format="json")
    assert resp.status_code == 400 and ReplacementPolicy.current().enabled is False
