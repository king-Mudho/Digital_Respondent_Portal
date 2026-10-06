"""Reopening links replaced by a second invitation (invitations.services.reopen_superseded_invitations, 2026-10-06).
Under test: a replaced link still in date works again when the case's newer invitation is still waiting, and the newer
one keeps working too; nothing reopens behind a revoked, started or submitted newer invitation, a link past its date,
or a revoked link; a dry run changes nothing; each reopened link is audited; and a later invitation closes them all."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import (
    TokenValidationError,
    issue_invitation,
    reopen_superseded_invitations,
    revoke_token,
    validate_token,
)


def _whatsapp_then_email(case):
    old_raw, _, old = issue_invitation(case, channel="WHATSAPP")
    new_raw, _, new = issue_invitation(case, channel="EMAIL")
    old.refresh_from_db()
    assert old.status == TokenStatus.EXPIRED
    return old_raw, old, new_raw, new


def test_a_replaced_link_works_again_alongside_the_newer_one(main_case):
    old_raw, old, new_raw, new = _whatsapp_then_email(main_case)
    with pytest.raises(TokenValidationError):
        validate_token(old_raw)

    result = reopen_superseded_invitations(apply=True)
    assert [e["token_id"] for e in result["reopened"]] == [old.pk]
    old.refresh_from_db()
    assert old.status == TokenStatus.SENT and old.expires_at > timezone.now()
    assert validate_token(old_raw).pk == old.pk  # the WhatsApp message works again
    assert validate_token(new_raw).pk == new.pk  # and so does the email
    event = AuditEvent.objects.get(action="invitation.reopened")
    assert event.object_id == str(old.pk) and event.metadata["newer_invitation"] == new.pk


def test_a_dry_run_changes_nothing(main_case):
    old_raw, old, _, _ = _whatsapp_then_email(main_case)
    out = StringIO()
    call_command("reopen_superseded_invitations", stdout=out)
    assert "Would reopen 1 links on 1 cases" in out.getvalue() and "Nothing was changed" in out.getvalue()
    old.refresh_from_db()
    assert old.status == TokenStatus.EXPIRED and not AuditEvent.objects.filter(action="invitation.reopened").exists()
    call_command("reopen_superseded_invitations", "--apply", stdout=StringIO())
    old.refresh_from_db()
    assert old.status == TokenStatus.SENT


@pytest.mark.parametrize("newer_status", [TokenStatus.SURVEY_STARTED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED])
def test_nothing_reopens_once_the_questionnaire_has_begun(main_case, newer_status):
    _, old, _, new = _whatsapp_then_email(main_case)
    InvitationToken.objects.filter(pk=new.pk).update(status=newer_status)
    assert reopen_superseded_invitations(apply=True)["reopened"] == []
    old.refresh_from_db()
    assert old.status == TokenStatus.EXPIRED


def test_nothing_reopens_behind_a_revoked_or_expired_newer_invitation(main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    _, old, _, new = _whatsapp_then_email(main_case)
    revoke_token(new, "Wrong person")
    other = create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026)
    _, other_old, _, other_new = _whatsapp_then_email(other)
    InvitationToken.objects.filter(pk=other_new.pk).update(expires_at=timezone.now() - timedelta(days=1))
    result = reopen_superseded_invitations(apply=True)
    assert result["reopened"] == [] and {e["token_id"] for e in result["skipped"]} == {old.pk, other_old.pk}


def test_a_link_past_its_own_date_and_a_revoked_link_stay_closed(main_case):
    _, old, _, _ = _whatsapp_then_email(main_case)
    InvitationToken.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    revoked_raw, _, revoked = issue_invitation(main_case, channel="SMS")
    revoke_token(revoked, "Sent to the wrong number")
    issue_invitation(main_case, channel="EMAIL")
    reopen_superseded_invitations(apply=True)
    old.refresh_from_db()
    revoked.refresh_from_db()
    assert old.status == TokenStatus.EXPIRED and revoked.status == TokenStatus.REVOKED


def test_a_later_invitation_closes_the_reopened_links_again(main_case):
    old_raw, old, new_raw, _ = _whatsapp_then_email(main_case)
    reopen_superseded_invitations(apply=True)
    issue_invitation(main_case, channel="WHATSAPP")
    for raw in (old_raw, new_raw):
        with pytest.raises(TokenValidationError):
            validate_token(raw)
