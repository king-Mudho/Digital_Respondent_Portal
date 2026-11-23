"""QA of key informant interviews, and assigning a KII record to a research assistant from its own page (PI, 23 Nov
2026). Under test:

- only the PI records a KII's QA decision -- not the Field Coordinator, the KII RA, the RA who did the interview, or
  the Supervisor; only a completed interview is checked; a query or rejection says why; each decision is audited;
- QA status and the assigned RA never change through a PATCH to the record;
- the record shows who it is assigned to and its QA; the register filters by both;
- /ra/callers/ lists the active Research Assistant (calls) accounts for the PI and Field Coordinator only, and
  /ra/assign-kii/ assigns and unassigns one record.
"""

import pytest

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.kii.models import KIIQAStatus, KIIStatus

from .test_research_assistants import _client, _user, team, work  # noqa: F401  (fixtures)


@pytest.fixture
def completed(work, team):
    record = work["kii"]
    record.status, record.interviewer = KIIStatus.COMPLETED, team["rudo"]
    record.save(update_fields=["status", "interviewer"])
    return record


def test_only_the_pi_records_a_kii_qa_decision(team, completed):
    url = f"/api/v1/kii/{completed.pk}/qa/"
    others = [team["fc"], team["rudo"], _user(Role.KII_RA, "kii_qa_ra"), _user(Role.SUPERVISOR_READONLY, "kii_qa_sup"),
              _user(Role.QUAN_QA_RA, "kii_qa_quan")]
    for user in others:
        assert _client(user).post(url, {"qa_status": "QA_PASSED"}, format="json").status_code == 403, user.username
    completed.refresh_from_db()
    assert completed.qa_status == KIIQAStatus.PENDING
    resp = _client(team["pi"]).post(url, {"qa_status": "QA_PASSED"}, format="json")
    assert resp.status_code == 200, resp.content
    assert (resp.json()["qa_status"], resp.json()["qa_by_name"]) == ("QA_PASSED", "Ra_Pi")
    event = AuditEvent.objects.get(action="kii.qa_decided")
    assert (event.metadata["from"], event.metadata["to"]) == ("PENDING", "QA_PASSED")


def test_a_query_or_rejection_says_why_and_only_a_completed_interview_is_checked(team, completed, work):
    pi = _client(team["pi"])
    url = f"/api/v1/kii/{completed.pk}/qa/"
    for status in ("QUERY", "REJECTED"):
        assert pi.post(url, {"qa_status": status}, format="json").status_code == 400
    assert pi.post(url, {"qa_status": "QUERY", "note": "Transcript cuts off at question 6"}, format="json").status_code == 200
    completed.refresh_from_db()
    assert (completed.qa_status, completed.qa_note[:10]) == (KIIQAStatus.QUERY, "Transcript")
    assert pi.post(url, {"qa_status": "NONSENSE"}, format="json").status_code == 400
    not_done = work["other_kii"]
    assert pi.post(f"/api/v1/kii/{not_done.pk}/qa/", {"qa_status": "QA_PASSED"}, format="json").status_code == 400
    not_done.refresh_from_db()
    assert not_done.qa_status == KIIQAStatus.PENDING


def test_qa_and_the_assigned_ra_never_change_through_a_patch(team, completed):
    resp = _client(team["pi"]).patch(f"/api/v1/kii/{completed.pk}/",
                                     {"qa_status": "QA_PASSED", "assigned_ra": team["tino"].id}, format="json")
    assert resp.status_code == 200
    completed.refresh_from_db()
    assert (completed.qa_status, completed.assigned_ra) == (KIIQAStatus.PENDING, None)


def test_assigning_from_the_record_page_and_the_register_filters(team, work):
    pi = _client(team["pi"])
    callers = pi.get("/api/v1/ra/callers/").json()
    assert {c["username"] for c in callers} == {"rudo", "tino"}
    assert _client(team["rudo"]).get("/api/v1/ra/callers/").status_code == 403
    record = work["kii"]
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": team["tino"].id, "kii_ids": [record.kii_id]}, format="json").json()["count"] == 1
    detail = pi.get(f"/api/v1/kii/{record.pk}/").json()
    assert (detail["assigned_ra"], detail["assigned_ra_name"]) == (team["tino"].id, "Tino")
    listed = pi.get("/api/v1/kii/", {"assigned_ra": team["tino"].id}).json()["results"]
    assert [r["kii_id"] for r in listed] == [record.kii_id]
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": None, "kii_ids": [record.kii_id]}, format="json").json()["count"] == 1
    record.refresh_from_db()
    assert record.assigned_ra is None


def test_the_register_filters_completed_interviews_by_qa(team, completed, work):
    pi = _client(team["pi"])
    rows = pi.get("/api/v1/kii/", {"status": "COMPLETED", "qa_status": "PENDING"}).json()["results"]
    assert [r["kii_id"] for r in rows] == [completed.kii_id]
    pi.post(f"/api/v1/kii/{completed.pk}/qa/", {"qa_status": "QA_PASSED"}, format="json")
    assert pi.get("/api/v1/kii/", {"status": "COMPLETED", "qa_status": "PENDING"}).json()["results"] == []
