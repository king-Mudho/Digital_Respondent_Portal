"""
Batch KII invitations (apps/kii/batch.py). Mail goes to Django's in-memory outbox. What is under test is that a batch
only ever invites KII records never invited before, in the groups chosen, with a contact and no open link; that every
email carries a working link to its own record; that a message which fails leaves no live link and no false
"Invited" behind; that it shares the Main-400 caps; that WhatsApp waits for Meta's approval of the KII template; and
that only the PI and Field Coordinator can start one.
"""

import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import Mock, patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.invitations import batch as main
from apps.invitations.batch import BatchError
from apps.invitations.models import Channel, InvitationBatch, InvitationBatchStatus
from apps.kii import batch as kb
from apps.kii.models import KIIInvitationToken, KIIInvitationTokenStatus, KIIStatus
from apps.kii.services import create_kii_record, validate_kii_token
from apps.messaging import twilio_client as tw

DELAY = "apps.kii.batch_views.send_invitation_batch.delay"
BATCH = "/api/v1/kii-invitations/batch/"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fast(settings, monkeypatch):
    settings.INVITATION_EMAIL_PAUSE_SECONDS = 0
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [])


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _user():
    role, _ = Role.objects.get_or_create(name="FIELD_COORDINATOR")
    user, _ = User.objects.get_or_create(username="kii_batch_fc", defaults={"role": role})
    return user


def _record(name="Tendai Moyo", *, pool="CORE_60", email="informant@example.co.zw", phone="", status=KIIStatus.PROSPECT,
            organisation="Agri Bank"):
    metadata = {"organisation_name": organisation}
    if pool:
        metadata["pool"] = pool
    return create_kii_record(participant_name=name, participant_role="Head of Agribusiness", stakeholder_category="Bank",
                             status=status, email=email, phone=phone, metadata=metadata)


def _open_link(record, *, expired=False):
    now = timezone.now()
    return KIIInvitationToken.objects.create(
        kii_record=record, token_hash=f"test-{record.pk}-{expired}", status=KIIInvitationTokenStatus.SENT,
        channel=Channel.EMAIL, issued_at=now - timedelta(days=20 if expired else 1),
        expires_at=now - timedelta(days=6) if expired else now + timedelta(days=13),
    )


def test_only_records_never_invited_with_a_contact_and_no_open_link_are_picked():
    ready = _record()
    expired_before = _record()
    _open_link(expired_before, expired=True)
    open_link = _record()
    _open_link(open_link)
    no_contact = _record(email="")
    picked_up = {status: _record(status=status) for status in (KIIStatus.INVITED, KIIStatus.SCHEDULED, KIIStatus.COMPLETED,
                                                             KIIStatus.DECLINED, KIIStatus.NO_SHOW)}
    phone_only = _record(email="", phone="0772123456")

    picked = set(kb.candidates().values_list("kii_id", flat=True))
    assert picked == {ready.kii_id, expired_before.kii_id}
    assert not picked & {open_link.kii_id, no_contact.kii_id, phone_only.kii_id, *[r.kii_id for r in picked_up.values()]}
    assert phone_only.kii_id in set(kb.candidates(("WHATSAPP",)).values_list("kii_id", flat=True))


def test_groups_are_chosen_core_60_first_and_unnamed_organisations_can_be_left_out():
    additional = _record(pool="ADDITIONAL")
    by_hand = _record(pool=None)
    reserve = _record(pool="RESERVE_30")
    core = _record(pool="CORE_60")
    unnamed = _record("Agri Bank (contact not yet identified)", pool="CORE_60")

    assert list(kb.candidates().values_list("kii_id", flat=True)) == [core.kii_id, unnamed.kii_id, reserve.kii_id,
                                                                      additional.kii_id, by_hand.kii_id]
    assert list(kb.candidates(groups=["CORE_60"]).values_list("kii_id", flat=True)) == [core.kii_id, unnamed.kii_id]
    assert set(kb.candidates(groups=["ADDITIONAL"]).values_list("kii_id", flat=True)) == {additional.kii_id, by_hand.kii_id}
    assert list(kb.candidates(groups=["CORE_60"], named_only=True).values_list("kii_id", flat=True)) == [core.kii_id]
    with pytest.raises(BatchError) as none:
        kb.start_batch(1, user=_user(), groups=[])
    assert none.value.code == "no_group"


def test_each_record_gets_one_email_with_a_working_link_to_its_own_invitation():
    first = _record("Tendai Moyo", email="first@example.co.zw", organisation="First Bank")
    second = _record("Rudo Chikore", email="second@example.co.zw", organisation="Second Bank")
    batch = kb.start_batch(2, user=_user())
    main.run_batch(batch.pk)  # the Celery task's entry point dispatches on mode
    batch.refresh_from_db()
    assert batch.mode == "KII" and batch.status == InvitationBatchStatus.DONE and batch.sent == 2 and batch.failed == 0
    assert sorted(m.to[0] for m in mail.outbox) == ["first@example.co.zw", "second@example.co.zw"]
    for record, address in ((first, "first@example.co.zw"), (second, "second@example.co.zw")):
        message = next(m for m in mail.outbox if m.to == [address])
        raw = re.search(r"/ki/([\w-]+)", message.body).group(1)
        assert validate_kii_token(raw).kii_record_id == record.pk  # the link opens this record's own invitation
        record.refresh_from_db()
        assert record.status == KIIStatus.INVITED and record.invitation_tokens.count() == 1
    assert AuditEvent.objects.filter(action="kii_invitation.emailed").count() == 2
    assert "@" not in str(batch.results).replace("***@", "")  # only masked addresses are kept
    assert AuditEvent.objects.filter(action="kii_invitations.batch_completed").exists()
    assert not kb.candidates().exists()  # nobody is invited twice


def test_a_failed_email_leaves_no_live_link_and_no_false_invited_status_and_the_rest_carry_on():
    failing = _record(email="fail@example.co.zw")
    fine = _record(email="fine@example.co.zw")
    batch = kb.start_batch(2, user=_user())
    with patch("django.core.mail.EmailMessage.send", side_effect=[SMTPException("refused"), 1]):
        main.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 1 and batch.failed == 1
    failing.refresh_from_db()
    fine.refresh_from_db()
    assert failing.status == KIIStatus.PROSPECT and not failing.invitation_tokens.exists()
    assert fine.status == KIIStatus.INVITED and fine.invitation_tokens.count() == 1
    assert [r["outcome"] for r in batch.results] == ["failed", "sent"]
    assert list(kb.candidates().values_list("kii_id", flat=True)) == [failing.kii_id]  # tried again next time


def test_the_caps_are_shared_with_main_400_emails(settings):
    for _ in range(3):
        _record()
    settings.INVITATION_EMAIL_BATCH_MAX = 2
    with pytest.raises(BatchError) as too_many:
        kb.start_batch(3, user=_user())
    assert too_many.value.code == "bad_limit"
    settings.INVITATION_EMAIL_BATCH_MAX, settings.INVITATION_EMAIL_DAILY_MAX = 100, 2
    AuditEvent.objects.create(action="invitation.emailed", object_type="InvitationToken", object_id="1", metadata={})
    AuditEvent.objects.create(action="kii_invitation.emailed", object_type="KIIInvitationToken", object_id="1", metadata={})
    assert main.left_today() == 0  # one Main-400 email and one KII email use up a limit of two
    with pytest.raises(BatchError) as daily:
        kb.start_batch(1, user=_user())
    assert daily.value.code == "daily_limit_reached"


def test_a_batch_stops_at_the_daily_cap_even_mid_batch(settings):
    for _ in range(3):
        _record()
    settings.INVITATION_EMAIL_DAILY_MAX = 2
    batch = kb.start_batch(2, user=_user())
    settings.INVITATION_EMAIL_DAILY_MAX = 1  # lowered while the batch was queued
    main.run_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.sent == 1 and len(mail.outbox) == 1


def test_a_record_invited_by_hand_after_the_batch_started_is_not_invited_again():
    record = _record()
    batch = kb.start_batch(1, user=_user())
    with patch.object(kb, "candidates", return_value=[record]):
        type(record).objects.filter(pk=record.pk).update(status=KIIStatus.INVITED)
        kb.run_batch(batch)
    assert batch.sent == 0 and batch.skipped == 1 and not mail.outbox


def test_whatsapp_waits_for_meta_to_approve_the_kii_template(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_WHATSAPP_FROM, settings.TWILIO_WA_CONTENT_KII_INVITATION = "+15550001111", "HXkii"
    settings.TWILIO_WA_CONTENT_INVITATION = "HXinvite"
    _record(email="", phone="0772123456")
    approvals = [{"sid": "HXkii", "status": "pending"}, {"sid": "HXinvite", "status": "pending"}]
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: approvals)
    with pytest.raises(BatchError) as waiting:
        kb.start_batch(1, user=_user(), channels=["WHATSAPP"])
    assert waiting.value.code == "whatsapp_template_not_approved" and "pending" in str(waiting.value)
    assert kb.summary(("WHATSAPP",))["channels"]["WHATSAPP"]["template_waiting"] == "pending"
    with pytest.raises(BatchError) as main_waiting:  # the Main-400 batch had the same gap
        main.start_batch(1, user=_user(), channels=["WHATSAPP"])
    assert main_waiting.value.code == "whatsapp_template_not_approved"

    approvals[0]["status"] = "approved"
    monkeypatch.setattr(tw.requests, "post", Mock(return_value=Mock(
        status_code=201, json=Mock(return_value={"sid": "SM0001", "status": "queued"}))))
    batch = kb.start_batch(1, user=_user(), channels=["WHATSAPP"])
    kb.run_batch(batch)
    assert batch.sent == 1 and "WhatsApp" in batch.results[0]["detail"]


def test_only_the_pi_and_coordinator_may_send_a_batch_and_the_preview_masks_addresses():
    _record("Tendai Moyo", email="tendai.moyo@example.co.zw")
    for role in ("CONTACT_RA", "KII_RA", "ANALYST", "DOC_RA"):
        client = _client(role, f"kii_batch_{role.lower()}")
        assert client.post(BATCH, {"limit": 1}, format="json").status_code == 403, role
    supervisor = _client("SUPERVISOR_READONLY", "kii_batch_sup")
    assert supervisor.get(BATCH).status_code == 200
    assert supervisor.post(BATCH, {"limit": 1}, format="json").status_code == 403
    assert APIClient().get(BATCH).status_code == 401
    coordinator = _client("FIELD_COORDINATOR", "kii_batch_fc_ok")
    info = coordinator.get(BATCH, {"groups": "CORE_60"}).data
    assert info["candidates"] == 1 and info["preview"][0]["email"] == "t***@example.co.zw"
    assert info["groups"]["CORE_60"] == 1 and "tendai.moyo@" not in str(info)
    assert coordinator.get(BATCH, {"groups": "RESERVE_30"}).data["candidates"] == 0
    with patch(DELAY) as delay:
        started = coordinator.post(BATCH, {"limit": 1, "channels": ["EMAIL"], "groups": ["CORE_60"]}, format="json")
    assert started.status_code == 202 and delay.call_count == 1 and started.data["mode"] == "KII"
    assert coordinator.get(f"{BATCH}{started.data['id']}/").data["requested"] == 1
    # The Main-400 screen neither shows nor serves a KII batch.
    assert coordinator.get("/api/v1/invitations/batch/").data["latest"] is None
    assert coordinator.get(f"/api/v1/invitations/batch/{started.data['id']}/").status_code == 404
    with patch(DELAY):
        assert coordinator.post(BATCH, {"limit": 1}, format="json").data["error"]["code"] == "already_running"
    assert InvitationBatch.objects.count() == 1
