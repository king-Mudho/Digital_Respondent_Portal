"""Renewing the links on the Research Assistants' call lists (invitations.renewal, PI request 8 Nov 2026). Under test:
an expired link on a Research Assistant's list works again -- the same link, with a new date and an audit entry -- for
Main-400 and KII alike; a link with plenty of time left is untouched; a dry run changes nothing; and nothing is renewed
for a LOCKED Reserve, a case not on a Research Assistant's list, a submitted case, a superseded or revoked link, a
duplicate, a refused case, a declined consent, or a KII informant who said no; the nightly task obeys its switch."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.renewal import renew_call_list_links
from apps.invitations.services import TokenValidationError, issue_invitation, revoke_token, validate_token
from apps.invitations.tasks import renew_call_list_links_task
from apps.kii.models import KIIInvitationToken, KIIStatus
from apps.kii.services import KIITokenValidationError, create_kii_record, issue_kii_invitation, validate_kii_token
from apps.sampling.models import ReserveStatus, SampleCase


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


@pytest.fixture
def ra(db):
    return _user("TELEPHONE_RA", "geyi_test")


def _expire(token, days_ago=3):
    type(token).objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(days=days_ago))
    token.refresh_from_db()


def _invited(case, ra, *, workflow="S05"):
    case.assigned_ra = ra
    case.save(update_fields=["assigned_ra"])
    raw, _, token = issue_invitation(case)
    SampleCase.objects.filter(pk=case.pk).update(workflow_status=workflow if case.sample_type == "MAIN" else None)
    _expire(token)
    return raw, token


def _kii_invited(ra):
    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Head", stakeholder_category="Bank",
                               metadata={"organisation_name": "CBZ Bank"}, phone="0772222222", assigned_ra=ra)
    raw, _, token = issue_kii_invitation(record)
    _expire(token)
    return record, raw, token


def test_an_expired_link_on_the_list_works_again_without_a_new_one(main_case, ra):
    raw, token = _invited(main_case, ra)
    with pytest.raises(TokenValidationError):
        validate_token(raw)

    result = renew_call_list_links(apply=True)
    assert [e["id"] for e in result["renewed"]] == [main_case.sample_id]
    assert validate_token(raw).pk == token.pk  # the same link they were sent
    token.refresh_from_db()
    assert token.expires_at > timezone.now() + timedelta(days=13)
    assert InvitationToken.objects.filter(sample_case=main_case).count() == 1  # nothing new issued
    event = AuditEvent.objects.get(action="invitation.renewed")
    assert event.object_id == str(token.pk) and event.metadata["previous_expiry"]


def test_a_kii_link_on_the_list_works_again(ra):
    record, raw, token = _kii_invited(ra)
    with pytest.raises(KIITokenValidationError):
        validate_kii_token(raw)
    renew_call_list_links(apply=True)
    assert validate_kii_token(raw).pk == token.pk
    assert AuditEvent.objects.filter(action="kii_invitation.renewed", object_id=str(token.pk)).exists()


def test_an_activated_reserve_is_renewed_but_a_locked_one_never(activated_reserve_case, ra):
    _, token = _invited(activated_reserve_case, ra)
    assert [e["id"] for e in renew_call_list_links()["renewed"]] == [activated_reserve_case.sample_id]
    SampleCase.objects.filter(pk=activated_reserve_case.pk).update(status=ReserveStatus.LOCKED)
    result = renew_call_list_links(apply=True)
    assert result["renewed"] == []
    token.refresh_from_db()
    assert token.expires_at < timezone.now()


def test_a_link_with_time_left_is_untouched(main_case, ra):
    _, token = _invited(main_case, ra)
    InvitationToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() + timedelta(days=10))
    assert renew_call_list_links(apply=True)["renewed"] == []
    assert renew_call_list_links(within_days=11)["renewed"]  # unless asked to look further ahead


def test_a_dry_run_changes_nothing(main_case, ra):
    raw, token = _invited(main_case, ra)
    out = StringIO()
    call_command("renew_invitation_links", stdout=out)
    assert "Would renew 1 Main-400 and 0 KII links" in out.getvalue() and "Nothing was changed" in out.getvalue()
    token.refresh_from_db()
    assert token.expires_at < timezone.now() and not AuditEvent.objects.filter(action="invitation.renewed").exists()
    call_command("renew_invitation_links", "--apply", stdout=StringIO())
    assert validate_token(raw).pk == token.pk


@pytest.mark.parametrize("assignee", ["CONTACT_RA", "PI_ADMIN", None])
def test_only_links_on_a_research_assistants_list(main_case, assignee):
    other = _user(assignee, "someone") if assignee else None
    _invited(main_case, other)
    _kii_invited(other)
    assert renew_call_list_links(apply=True)["renewed"] == []


def test_not_once_submitted(main_case, ra):
    _, token = _invited(main_case, ra)
    InvitationToken.objects.create(sample_case=main_case, token_hash="x$y", status=TokenStatus.SUBMITTED, invitation_wave=1,
                                   issued_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1))
    assert renew_call_list_links(apply=True)["renewed"] == []


def test_not_a_superseded_or_revoked_link(main_case, ra):
    old_raw, old = _invited(main_case, ra)
    new_raw, _, new = issue_invitation(main_case)
    _expire(new)
    revoke_token(new, "test")
    assert renew_call_list_links(apply=True)["renewed"] == []
    for raw in (old_raw, new_raw):
        with pytest.raises(TokenValidationError):
            validate_token(raw)


@pytest.mark.parametrize("change", ["duplicate", "refused", "declined", "withdrawn"])
def test_not_a_duplicate_or_someone_who_said_no(main_case, ra, change):
    _invited(main_case, ra)
    if change == "duplicate":
        SampleCase.objects.filter(pk=main_case.pk).update(metadata={"duplicate_of": "SID-2026-000001"})
    elif change == "refused":
        SampleCase.objects.filter(pk=main_case.pk).update(workflow_status="S12")
    else:
        record_consent(sample_case=main_case, consent_type=ConsentType.PARTICIPATION, information_sheet_version="v1.3",
                       decision=ConsentDecision.DECLINED if change == "declined" else ConsentDecision.WITHDRAWN,
                       method=ConsentMethod.WEB_CLICKTHROUGH)
    assert renew_call_list_links(apply=True)["renewed"] == []


def test_not_a_kii_informant_who_said_no(ra):
    record, _, token = _kii_invited(ra)
    type(record).objects.filter(pk=record.pk).update(status=KIIStatus.DECLINED)
    assert renew_call_list_links(apply=True)["renewed"] == []
    assert KIIInvitationToken.objects.get(pk=token.pk).expires_at < timezone.now()


def test_the_nightly_task_obeys_its_switch(main_case, ra, settings):
    _invited(main_case, ra)
    settings.INVITATION_AUTO_RENEW = False
    assert renew_call_list_links_task() == {"skipped": "INVITATION_AUTO_RENEW is off"}
    settings.INVITATION_AUTO_RENEW = True
    assert renew_call_list_links_task() == {"renewed": 1, "left": 0}
