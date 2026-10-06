"""
Batch email invitations (apps/invitations/batch.py). Mail goes to Django's in-memory outbox. What is under test is
that a batch only ever invites verified cases that may be invited, have an email and no open invitation; that it
stays inside its caps; that every email carries a working link to its own case; and that an email which fails
leaves no live link and no false "Invitation sent" behind.
"""

import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent
from apps.invitations import batch as b
from apps.invitations.models import (
    Channel,
    InvitationBatch,
    InvitationBatchStatus,
    InvitationToken,
    TokenStatus,
)
from apps.invitations.services import validate_token
from apps.sampling.models import ReserveStatus, SampleType
from apps.sampling.services import create_sample_case

DELAY = "apps.invitations.batch_views.send_invitation_batch.delay"
BATCH = "/api/v1/invitations/batch/"


@pytest.fixture(autouse=True)
def _fast(settings):
    settings.INVITATION_EMAIL_PAUSE_SECONDS = 0
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _user():
    role, _ = Role.objects.get_or_create(name="FIELD_COORDINATOR")
    user, _ = User.objects.get_or_create(username="batch_fc", defaults={"role": role})
    return user


def _ready(organisation, stratum, *, email="contact@example.co.zw", status="S03", sample_type=SampleType.MAIN, reserve=None):
    case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=sample_type, year=2026)
    case.workflow_status = status
    fields = ["workflow_status"]
    if reserve:
        case.status = reserve
        fields.append("status")
    case.save(update_fields=fields)
    if email is not None:
        Respondent.objects.create(sample_case=case, full_name="Rudo Chikore", email=email)
    return case


def _open_token(case, *, expired=False):
    now = timezone.now()
    return InvitationToken.objects.create(
        sample_case=case, token_hash=f"test-{case.pk}-{expired}", status=TokenStatus.SENT, channel=Channel.WHATSAPP, invitation_wave=1,
        issued_at=now - timedelta(days=20 if expired else 1), expires_at=now - timedelta(days=6) if expired else now + timedelta(days=13),
    )


def test_only_verified_invitable_cases_with_an_email_and_no_open_invitation_are_picked(organisation, stratum):
    s03 = _ready(organisation, stratum)
    s04 = _ready(organisation, stratum, status="S04")
    expired_before = _ready(organisation, stratum)
    _open_token(expired_before, expired=True)
    activated = _ready(organisation, stratum, sample_type=SampleType.RESERVE, reserve=ReserveStatus.ACTIVATED)
    unverified = _ready(organisation, stratum, status="S00")
    already_sent = _ready(organisation, stratum, status="S05")
    no_email = _ready(organisation, stratum, email=None)
    open_invitation = _ready(organisation, stratum)
    _open_token(open_invitation)
    locked = _ready(organisation, stratum, sample_type=SampleType.RESERVE, reserve=ReserveStatus.LOCKED)

    picked = set(b.batch_candidates().values_list("sample_id", flat=True))
    assert picked == {s03.sample_id, s04.sample_id, expired_before.sample_id, activated.sample_id}
    assert not picked & {unverified.sample_id, already_sent.sample_id, no_email.sample_id, open_invitation.sample_id, locked.sample_id}


def test_each_case_gets_one_email_with_a_working_link_to_its_own_invitation(organisation, stratum):
    first = _ready(organisation, stratum, email="first@example.co.zw")
    second = _ready(organisation, stratum, email="second@example.co.zw")
    batch = b.start_batch(2, user=_user())
    b.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.status == InvitationBatchStatus.DONE and batch.sent == 2 and batch.failed == 0
    assert sorted(m.to[0] for m in mail.outbox) == ["first@example.co.zw", "second@example.co.zw"]
    for case, address in ((first, "first@example.co.zw"), (second, "second@example.co.zw")):
        message = next(m for m in mail.outbox if m.to == [address])
        assert message.subject == f"{organisation.name}: invitation to take part in a Chinhoyi University of Technology research study"
        case.refresh_from_db()
        assert case.workflow_status == "S05"
        raw = re.search(r"/i/([\w-]+)", message.body).group(1)
        assert validate_token(raw).sample_case_id == case.pk  # the link opens this case's own invitation
        assert case.invitation_tokens.get().channel == Channel.EMAIL
    assert AuditEvent.objects.filter(action="invitation.emailed").count() == 2
    assert "@" not in str(batch.results).replace("***@", "")  # only masked addresses are kept
    assert AuditEvent.objects.filter(action="invitations.batch_completed").exists()


def test_a_failed_email_leaves_no_live_link_and_no_false_sent_status_and_the_rest_carry_on(organisation, stratum):
    failing = _ready(organisation, stratum, email="fail@example.co.zw")
    fine = _ready(organisation, stratum, email="fine@example.co.zw")
    batch = b.start_batch(2, user=_user())
    with patch("apps.invitations.messages.EmailMessage.send", side_effect=[SMTPException("refused"), 1]):
        b.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 1 and batch.failed == 1
    failing.refresh_from_db()
    fine.refresh_from_db()
    assert failing.workflow_status == "S03" and not failing.invitation_tokens.exists()
    assert fine.workflow_status == "S05" and fine.invitation_tokens.count() == 1
    assert [r["outcome"] for r in batch.results] == ["failed", "sent"]
    # The failed case is picked up again by the next batch.
    assert list(b.batch_candidates().values_list("sample_id", flat=True)) == [failing.sample_id]


def test_the_per_batch_and_daily_caps_are_enforced(organisation, stratum, settings):
    for _ in range(3):
        _ready(organisation, stratum)
    settings.INVITATION_EMAIL_BATCH_MAX = 2
    with pytest.raises(b.BatchError) as too_many:
        b.start_batch(3, user=_user())
    assert too_many.value.code == "bad_limit"
    settings.INVITATION_EMAIL_BATCH_MAX, settings.INVITATION_EMAIL_DAILY_MAX = 100, 1
    some_case = _ready(organisation, stratum)
    AuditEvent.objects.create(action="invitation.emailed", object_type="InvitationToken", object_id="1", metadata={})
    assert b.left_today() == 0
    with pytest.raises(b.BatchError) as daily:
        b.start_batch(1, user=_user())
    assert daily.value.code == "daily_limit_reached" and some_case.pk


def test_a_batch_stops_at_the_daily_cap_even_mid_batch(organisation, stratum, settings):
    for _ in range(3):
        _ready(organisation, stratum)
    settings.INVITATION_EMAIL_DAILY_MAX = 2
    batch = b.start_batch(2, user=_user())
    settings.INVITATION_EMAIL_DAILY_MAX = 1  # lowered while the batch was queued
    b.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 1 and len(mail.outbox) == 1


def test_nothing_starts_without_email_set_up_or_while_another_batch_is_sending(organisation, stratum, settings):
    _ready(organisation, stratum)
    coordinator = _client("FIELD_COORDINATOR", "batch_fc_api")
    InvitationBatch.objects.create(requested=1)  # still RUNNING
    with patch(DELAY) as delay:
        running = coordinator.post(BATCH, {"limit": 1}, format="json")
        settings.EMAIL_BACKEND, settings.EMAIL_HOST = "django.core.mail.backends.smtp.EmailBackend", ""
        no_email = coordinator.post(BATCH, {"limit": 1}, format="json")
    assert running.status_code == 409 and running.data["error"]["code"] == "already_running"
    assert no_email.status_code == 503 and no_email.data["error"]["code"] == "email_not_configured"
    delay.assert_not_called()


def test_only_the_pi_and_coordinator_may_send_a_batch_and_the_preview_masks_addresses(organisation, stratum):
    _ready(organisation, stratum, email="rudo.chikore@example.co.zw")
    for role in ("CONTACT_RA", "KII_RA", "ANALYST"):
        client = _client(role, f"batch_{role.lower()}")
        assert client.post(BATCH, {"limit": 1}, format="json").status_code == 403, role
    supervisor = _client("SUPERVISOR_READONLY", "batch_sup")
    assert supervisor.get(BATCH).status_code == 200
    assert supervisor.post(BATCH, {"limit": 1}, format="json").status_code == 403
    assert APIClient().get(BATCH).status_code == 401
    coordinator = _client("FIELD_COORDINATOR", "batch_fc_ok")
    info = coordinator.get(BATCH).data
    assert info["candidates"] == 1 and info["preview"][0]["email"] == "r***@example.co.zw"
    assert "rudo.chikore@" not in str(info)
    with patch(DELAY) as delay:
        started = coordinator.post(BATCH, {"limit": 1}, format="json")
    assert started.status_code == 202 and delay.call_count == 1
    progress = coordinator.get(f"{BATCH}{started.data['id']}/")
    assert progress.status_code == 200 and progress.data["requested"] == 1
