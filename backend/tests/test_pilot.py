"""The ZAS 2026 pilot as its own strand beside the main study (apps/kobo/pilot.py, PI decision 8 Nov 2026). KoboToolbox
is a fake requests.get. Under test:

- every pilot submission becomes a PilotRecord; nothing becomes a SampleCase, QUANSubmission, KIIRecord or
  DocumentRecord, so the Main-400 sample and its exports are untouched;
- a respondent who declined consent is never counted, whatever anyone decides;
- non-standard and shared interview IDs are flagged for the PI, and the PI's include/exclude decision (with a reason
  for an exclusion) survives a re-sync and is audited; a submission deleted in Kobo stops counting;
- the dashboards add the pilot beside the main figures, never inside them;
- the list shows a summary with answer labels, never the answers; only the PI syncs or decides.
"""

from unittest.mock import Mock

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.kobo import pilot
from apps.kobo.models import PilotRecord, QUANSubmission
from apps.sampling.models import SampleCase

QUAN_UID, KII_UID, DOC_UID = "aQuanPilot", "aKiiPilot", "aDocPilot"
LIKERT = [{"list_name": "agree", "name": "4", "label": ["Agree"]}]
CONTENT = {
    QUAN_UID: {"survey": [{"name": "PROF01", "select_from_list_name": "orgtype"}, {"name": "PROF06", "select_from_list_name": "prov"}],
               "choices": [{"list_name": "orgtype", "name": "commercial_bank", "label": [None, "Commercial bank"]},
                           {"list_name": "prov", "name": "harare", "label": ["Harare"]}, *LIKERT]},
    KII_UID: {"survey": [], "choices": []},
    DOC_UID: {"survey": [], "choices": []},
}


def quan(kobo_id, ref, consent="yes"):
    return {"_id": kobo_id, "_submission_time": "2026-08-25T11:07:52", "admin_consent/ADM01": ref,
            "admin_consent/ADM02": "2026-08-25", "admin_consent/CONSENT01": consent, "profile/PROF01": "commercial_bank",
            "profile/PROF06": "harare", "nfm/NFM01": "4", "_attachments": []}


@pytest.fixture
def kobo(settings):
    settings.KOBO_API_TOKEN, settings.KOBO_API_BASE_URL = "token", "https://kf.example.org"
    settings.KOBO_PILOT_FORMS = [f"quan:QUAN:{QUAN_UID}", f"kii_exec:KII:{KII_UID}", f"docs:DOCUMENT:{DOC_UID}"]
    data = {
        QUAN_UID: [quan(1, "ZAS26-001"), quan(2, "ZAS26-003"), quan(3, "ZAS26-003 "), quan(4, "Ernest Q1"), quan(5, "ZAS26-009", "no")],
        KII_UID: [{"_id": 11, "interview_id": "EX-1", "interview_date": "2026-08-26", "consent": "yes", "respondent_category": "bank"}],
        DOC_UID: [{"_id": 21, "DOC01": "PD-01", "DOC02": "Agricultural Finance Policy", "DOC03": "Ministry", "DOC05": 2024}],
    }

    def get(url, headers=None, timeout=None):
        assert headers == {"Authorization": "Token token"}
        uid = url.split("/assets/")[1].split("/")[0]
        body = {"results": data[uid]} if "/data/" in url else {"content": CONTENT[uid]}
        return Mock(status_code=200, json=Mock(return_value=body))

    return data, get


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def test_pilot_submissions_become_their_own_records_and_nothing_in_the_main_sample(db, kobo, main_case):
    data, get = kobo
    stats = pilot.sync(get=get)
    assert stats["quan"] == {"added": 5, "updated": 0, "gone": 0}
    assert PilotRecord.objects.count() == 7
    assert (QUANSubmission.objects.count(), SampleCase.objects.count()) == (0, 1)  # main sample untouched
    assert pilot.counts() == {"quan": 4, "kii": 1, "documents": 1}  # the declined consent never counts

    declined = PilotRecord.objects.get(kobo_id=5)
    assert (declined.included, declined.consented, declined.exclusion_reason) == (False, False, pilot.DECLINED)
    shared = PilotRecord.objects.get(kobo_id=3)
    assert shared.reference == "ZAS26-003" and "Interview ID shared by 2 submissions" in shared.flags
    assert any(f.startswith("Non-standard interview ID") for f in PilotRecord.objects.get(kobo_id=4).flags)
    assert PilotRecord.objects.get(kobo_id=1).flags == []
    first = PilotRecord.objects.get(kobo_id=1)
    assert first.summary["Organisation type"] == "Commercial bank" and first.summary["Province"] == "Harare"
    assert str(first.collected_on) == "2026-08-25" and first.payload["nfm/NFM01"] == "4"
    assert PilotRecord.objects.get(kobo_id=21).summary["Title"] == "Agricultural Finance Policy"
    assert AuditEvent.objects.filter(action="pilot.record_added").count() == 7


def test_the_pis_decision_survives_a_resync_and_a_declined_consent_can_never_count(db, kobo):
    data, get = kobo
    pilot.sync(get=get)
    pi = User.objects.create_user(username="pilot_pi", password="x", role=Role.objects.get_or_create(name=Role.PI_ADMIN)[0])
    practice = PilotRecord.objects.get(kobo_id=4)
    with pytest.raises(pilot.PilotError):
        pilot.decide(pi, practice.pk, included=False)  # a reason is required
    pilot.decide(pi, practice.pk, included=False, reason="RA practice run on the first morning")
    with pytest.raises(pilot.PilotError):
        pilot.decide(pi, PilotRecord.objects.get(kobo_id=5).pk, included=True)
    assert AuditEvent.objects.filter(action="pilot.decision").count() == 1

    pilot.sync(get=get)
    practice.refresh_from_db()
    assert (practice.included, practice.exclusion_reason) == (False, "RA practice run on the first morning")
    assert pilot.counts()["quan"] == 3

    data[QUAN_UID].pop(0)  # deleted in KoboToolbox
    pilot.sync(get=get)
    gone = PilotRecord.objects.get(kobo_id=1)
    assert (gone.included, gone.exclusion_reason) == (False, pilot.GONE) and pilot.counts()["quan"] == 2


def test_the_dashboards_show_the_pilot_beside_the_main_figures_not_inside_them(db, kobo):
    _, get = kobo
    pilot.sync(get=get)
    auth_client = _client(Role.PI_ADMIN, "pilot_dash_pi")
    executive = auth_client.get("/api/v1/dashboards/executive/").json()
    assert (executive["quan_completed"], executive["quan_pilot"]) == (0, 4)
    assert (executive["kii_completed"], executive["kii_pilot"]) == (0, 1)
    assert (executive["documents_coded"], executive["documents_pilot"]) == (0, 1)
    kii_docs = auth_client.get("/api/v1/dashboards/kii-documents/").json()
    assert (kii_docs["kii_completed"], kii_docs["kii_pilot"], kii_docs["documents_pilot"]) == (0, 1, 1)
    kpis = auth_client.get("/api/v1/reports/overview/").json()["kpis"]
    assert (kpis["quan_pilot"], kpis["kii_pilot"], kpis["documents_pilot"]) == (4, 1, 1)


def test_the_list_never_carries_answers_and_only_the_pi_syncs_or_decides(db, kobo, monkeypatch):
    _, get = kobo
    pilot.sync(get=get)
    fc = _client(Role.FIELD_COORDINATOR, "pilot_fc")
    body = fc.get("/api/v1/pilot/").json()
    assert body["counts"] == {"quan": 4, "kii": 1, "documents": 1}
    assert all("payload" not in r for r in body["results"]) and len(body["results"]) == 7
    assert [t["included"] for t in body["totals"]] == [4, 1, 1]
    assert len(fc.get("/api/v1/pilot/", {"show": "flagged"}).json()["results"]) == 3
    assert len(fc.get("/api/v1/pilot/", {"show": "excluded"}).json()["results"]) == 1

    record = PilotRecord.objects.get(kobo_id=4)
    assert fc.post(f"/api/v1/pilot/{record.pk}/decision/", {"included": False, "reason": "x"}, format="json").status_code == 403
    assert fc.post("/api/v1/pilot/sync/").status_code == 403
    assert _client(Role.CONTACT_RA, "pilot_ra").get("/api/v1/pilot/").status_code == 403
    pi = _client(Role.PI_ADMIN, "pilot_pi2")
    resp = pi.post(f"/api/v1/pilot/{record.pk}/decision/", {"included": False, "reason": "Practice"}, format="json")
    assert resp.status_code == 200 and resp.json()["included"] is False
    monkeypatch.setattr(pilot.requests, "get", get)
    assert pi.post("/api/v1/pilot/sync/").status_code == 200
