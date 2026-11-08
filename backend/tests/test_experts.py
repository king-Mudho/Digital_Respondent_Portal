"""The ABI expert content-validation panel (apps/experts, 2026-11-08). Under test:

- experts are registered with their details and get sequential coded IDs (E01, E02, ...);
- no invitation goes out until the ethics approval reference is recorded, nor once 12 experts have completed;
- the questionnaire link is refused until the expert has consented on the portal (AGENTS.md rule 6), and carries only
  the Expert ID, never the name; a decline closes the record;
- a questionnaire in KoboToolbox completes a consented expert, never one who did not consent;
- PI and Field Coordinator manage the panel, the Supervisor reads, the Analyst and RAs are refused;
- no message or questionnaire text an expert reads contains a forbidden word (AGENTS.md rule 2).
"""

import re

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.experts import instrument
from apps.experts.models import ExpertRecord, ExpertStatus
from apps.experts.services import mark_completed_from_kobo

FORBIDDEN = ["approved", "loan approval", "credit rating", "bankability score", "guarantee"]


def _client(role_name, username=None):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username or f"exp_{role_name.lower()}", password="x", role=role))
    return client


@pytest.fixture
def pi(db):
    return _client(Role.PI_ADMIN, "exp_pi")


@pytest.fixture
def open_panel(settings):
    settings.EXPERT_ETHICS_REFERENCE = "CUT/ETH/2026/123"
    settings.KOBO_EXPERT_FORM_URL = "https://ee.kobotoolbox.org/x/ExpertForm"
    settings.EXPERT_TARGET = 12


def _register(client, name="Dr Tendai Moyo", area="FINANCE", **extra):
    body = {"full_name": name, "panel_area": area, "title": "Head of Agricultural Finance", "institution": "AFC Bank",
            "email": "t.moyo@example.org", "whatsapp_number": "0772 111 222", **extra}
    resp = client.post("/api/v1/experts/", body, format="json")
    assert resp.status_code == 201, resp.content
    return resp.json()


def _invite(client, expert_id):
    return client.post("/api/v1/expert-invitations/", {"expert_id": expert_id, "channel": "EMAIL",
                                                       "link_base": "https://research.agribizframework.com"}, format="json")


def test_experts_are_registered_with_coded_ids(pi):
    first, second = _register(pi), _register(pi, "Prof Rudo Chari", "METHODS")
    assert (first["expert_id"], second["expert_id"]) == ("E01", "E02")
    assert first["status"] == "PROSPECT"
    assert pi.post("/api/v1/experts/", {"full_name": "No area"}, format="json").status_code == 400
    body = pi.get("/api/v1/experts/").json()
    finance = next(p for p in body["panel"] if p["area"] == "FINANCE")
    assert (finance["target"], finance["registered"], body["target"]) == (3, 1, 12)
    assert AuditEvent.objects.filter(action="expert.registered").count() == 2


def test_no_invitation_before_the_ethics_reference_is_recorded(pi, settings):
    settings.EXPERT_ETHICS_REFERENCE = ""
    expert = _register(pi)
    resp = _invite(pi, expert["expert_id"])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "invitations_closed"
    assert "ethics approval reference" in pi.get("/api/v1/experts/").json()["invitations_closed"]


def test_the_invitation_carries_a_personal_link_and_no_forbidden_word(pi, open_panel):
    expert = _register(pi)
    resp = _invite(pi, expert["expert_id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["link"].startswith("https://research.agribizframework.com/ex/")
    assert body["whatsapp_to"] == "263772111222" and body["email_to"] == "t.moyo@example.org"
    assert body["raw_manual_code"] in body["messages"]["email_body"] and body["link"] in body["messages"]["whatsapp"]
    everything = " ".join(body["messages"].values()) + " " + instrument.all_text()
    assert not [p for p in FORBIDDEN if re.search(r"(?<![\w])" + re.escape(p), everything, re.IGNORECASE)]
    assert ExpertRecord.objects.get(expert_id="E01").status == ExpertStatus.INVITED


def test_the_questionnaire_opens_only_after_consent_and_carries_only_the_expert_id(pi, open_panel):
    expert = _register(pi)
    token = _invite(pi, expert["expert_id"]).json()["link"].rsplit("/ex/", 1)[1]
    public = APIClient()
    valid = public.get("/api/v1/expert-invitations/validate/", {"t": token}).json()
    assert valid["expert_name"] == "Dr Tendai Moyo" and len(valid["consent_statements"]) == 3

    refused = public.get("/api/v1/expert-invitations/kobo-redirect-url/", {"t": token})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "consent_required"

    assert public.post("/api/v1/expert-consent/", {"token": token, "decision": "GIVEN"}, format="json").status_code == 200
    url = public.get("/api/v1/expert-invitations/kobo-redirect-url/", {"t": token}).json()["kobo_form_url"]
    assert url == "https://ee.kobotoolbox.org/x/ExpertForm?d[part_a/EXPERT_ID]=E01"
    assert "Moyo" not in url
    assert ExpertRecord.objects.get(expert_id="E01").status == ExpertStatus.CONSENTED


def test_a_decline_closes_the_record_and_no_new_link_follows(pi, open_panel):
    expert = _register(pi)
    token = _invite(pi, expert["expert_id"]).json()["link"].rsplit("/ex/", 1)[1]
    public = APIClient()
    public.post("/api/v1/expert-consent/", {"token": token, "decision": "DECLINED"}, format="json")
    assert ExpertRecord.objects.get(expert_id="E01").status == ExpertStatus.DECLINED
    assert public.get("/api/v1/expert-invitations/kobo-redirect-url/", {"t": token}).status_code == 403
    assert _invite(pi, expert["expert_id"]).json()["error"]["code"] == "not_invitable"


def test_a_kobo_submission_completes_only_a_consented_expert_and_the_panel_closes_at_the_target(pi, open_panel, settings):
    consented, silent = _register(pi), _register(pi, "Mr Silent", "AGRIBUSINESS")
    token = _invite(pi, consented["expert_id"]).json()["link"].rsplit("/ex/", 1)[1]
    APIClient().post("/api/v1/expert-consent/", {"token": token, "decision": "GIVEN"}, format="json")
    assert mark_completed_from_kobo(["E01", "E02"]) == 1
    statuses = dict(ExpertRecord.objects.values_list("expert_id", "status"))
    assert statuses == {"E01": ExpertStatus.COMPLETED, "E02": ExpertStatus.PROSPECT}
    assert pi.get("/api/v1/dashboards/executive/").json()["experts_completed"] == 1

    settings.EXPERT_TARGET = 1
    resp = _invite(pi, silent["expert_id"])
    assert resp.status_code == 409 and "panel is complete" in resp.json()["error"]["message"]


def test_the_form_sync_completes_experts_from_their_kobo_submissions(pi, open_panel, monkeypatch):
    from apps.kobo import form_sync

    expert = _register(pi)
    token = _invite(pi, expert["expert_id"]).json()["link"].rsplit("/ex/", 1)[1]
    APIClient().post("/api/v1/expert-consent/", {"token": token, "decision": "GIVEN"}, format="json")
    form_sync._link_records("experts", [{"part_a/EXPERT_ID": "E01", "_id": 1}])
    assert ExpertRecord.objects.get(expert_id="E01").status == ExpertStatus.COMPLETED


def test_who_may_manage_and_read_the_panel(pi, open_panel):
    _register(pi)
    fc = _client(Role.FIELD_COORDINATOR)
    assert fc.post("/api/v1/experts/", {"full_name": "FC adds", "panel_area": "ECONOMICS"}, format="json").status_code == 201
    supervisor = _client(Role.SUPERVISOR_READONLY)
    assert supervisor.get("/api/v1/experts/").status_code == 200
    assert supervisor.post("/api/v1/experts/", {"full_name": "x", "panel_area": "ECONOMICS"}, format="json").status_code == 403
    assert _invite(supervisor, "E01").status_code == 403
    for role in (Role.ANALYST, Role.KII_RA, Role.CONTACT_RA):
        assert _client(role).get("/api/v1/experts/").status_code == 403, role


def test_an_email_is_sent_only_with_the_invitations_own_link(pi, open_panel, settings):
    settings.EMAIL_HOST = "smtp.example.org"
    expert = _register(pi)
    issued = _invite(pi, expert["expert_id"]).json()
    url = f"/api/v1/expert-invitations/{issued['token_id']}/send-email/"
    bad = pi.post(url, {"link": issued["link"] + "x", "manual_code": issued["raw_manual_code"]}, format="json")
    assert bad.status_code in (400, 503)


def test_staff_record_a_decline_but_never_consent_or_completion(pi):
    expert = _register(pi)
    url = f"/api/v1/experts/{expert['expert_id']}/"
    assert pi.patch(url, {"status": "COMPLETED"}, format="json").status_code == 400
    assert pi.patch(url, {"status": "DECLINED", "notes": "Declined by phone"}, format="json").json()["status"] == "DECLINED"
