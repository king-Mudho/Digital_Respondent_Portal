"""WhatsApp send queue (apps/invitations/whatsapp_queue.py): verified cases with a number and no open invitation, one
tap each. Under test: only the right cases are queued, a Contact RA sees and prepares only their own, preparing issues
a real WhatsApp invitation whose link works, and a case cannot be prepared twice."""

import re
from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent
from apps.invitations.models import Channel, InvitationToken, TokenStatus
from apps.invitations.services import validate_token
from apps.sampling.models import ReserveStatus, SampleType
from apps.sampling.services import create_sample_case

QUEUE = "/api/v1/invitations/whatsapp-queue/"


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _case(organisation, stratum, *, phone="0773943709", status="S03", sample_type=SampleType.MAIN, reserve=None, ra=None):
    case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=sample_type, year=2026)
    case.workflow_status, case.assigned_ra = status, ra
    fields = ["workflow_status", "assigned_ra"]
    if reserve:
        case.status = reserve
        fields.append("status")
    case.save(update_fields=fields)
    if phone is not None:
        Respondent.objects.create(sample_case=case, full_name="Rudo Chikore", phone=phone)
    return case


@pytest.fixture
def coordinator(db):
    return _client(_user("FIELD_COORDINATOR", "wa_fc"))


def test_only_verified_invitable_cases_with_a_number_and_no_open_invitation_are_queued(organisation, stratum, coordinator):
    ready = _case(organisation, stratum)
    s04 = _case(organisation, stratum, status="S04")
    _case(organisation, stratum, status="S00")
    _case(organisation, stratum, phone=None)
    _case(organisation, stratum, sample_type=SampleType.RESERVE, reserve=ReserveStatus.LOCKED)
    invited = _case(organisation, stratum)
    now = timezone.now()
    InvitationToken.objects.create(sample_case=invited, token_hash="wa-open", status=TokenStatus.SENT, channel=Channel.EMAIL,
                                   invitation_wave=1, issued_at=now, expires_at=now + timedelta(days=10))
    body = coordinator.get(QUEUE).json()
    assert {r["sample_id"] for r in body["results"]} == {ready.sample_id, s04.sample_id}
    assert body["results"][0]["number"] == "+263 ••• 709"  # masked in the list


def test_preparing_issues_a_whatsapp_invitation_whose_link_opens_that_case(organisation, stratum, coordinator):
    case = _case(organisation, stratum)
    resp = coordinator.post(f"{QUEUE}{case.sample_id}/prepare/", {}, format="json")
    assert resp.status_code == 201
    url = resp.data["whatsapp_url"]
    assert url.startswith("https://wa.me/263773943709?text=")
    raw = re.search(r"/i/([\w-]+)", unquote(url)).group(1)
    token = InvitationToken.objects.get(sample_case=case)
    assert token.channel == Channel.WHATSAPP and "quote code" in resp.data["message"]
    case.refresh_from_db()
    assert case.workflow_status == "S05"
    assert validate_token(raw).sample_case_id == case.pk
    again = coordinator.post(f"{QUEUE}{case.sample_id}/prepare/", {}, format="json")
    assert again.status_code == 409 and again.data["error"]["code"] == "not_in_queue"  # never two live links


def test_a_contact_ra_sees_and_prepares_only_their_own_cases(organisation, stratum):
    mine_ra, other_ra = _user("CONTACT_RA", "wa_cra"), _user("CONTACT_RA", "wa_cra2")
    mine = _case(organisation, stratum, ra=mine_ra)
    theirs = _case(organisation, stratum, ra=other_ra)
    client = _client(mine_ra)
    assert [r["sample_id"] for r in client.get(QUEUE).json()["results"]] == [mine.sample_id]
    assert client.post(f"{QUEUE}{theirs.sample_id}/prepare/", {}, format="json").status_code == 409
    assert not InvitationToken.objects.filter(sample_case=theirs).exists()
    assert client.post(f"{QUEUE}{mine.sample_id}/prepare/", {}, format="json").status_code == 201


def test_roles_outside_contact_work_are_refused_and_the_supervisor_only_reads(organisation, stratum):
    case = _case(organisation, stratum)
    for role in ("KII_RA", "DOCUMENTARY_RA", "QUAN_QA_RA", "ANALYST"):
        client = _client(_user(role, f"wa_{role.lower()}"))
        assert client.get(QUEUE).status_code == 403, role
    supervisor = _client(_user("SUPERVISOR_READONLY", "wa_sup"))
    assert supervisor.get(QUEUE).status_code == 200
    assert supervisor.post(f"{QUEUE}{case.sample_id}/prepare/", {}, format="json").status_code == 403
    assert APIClient().get(QUEUE).status_code == 401
