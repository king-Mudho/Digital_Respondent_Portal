"""The research assistant who found an organisation or informant (PI, 23 Nov 2026). Under test:

- a completion of something an RA found is credited to that RA, even when another RA's call came last or the PI sent
  every message; administered if they filled it in themselves, otherwise assisted -- and paid once QA passes;
- nothing an RA found is taken from them: not by a bulk move, an unassignment, the sample bulk assignment, or the
  new-link rotation;
- only the PI records a finder, for named records, and it is audited.
"""

from decimal import Decimal

import pytest

from apps.audit.models import AuditEvent
from apps.kii.models import KIIQAStatus, KIIStatus
from apps.kobo.models import QAStatus
from apps.ra import credit
from apps.ra.assignment import assign_on_link
from apps.ra.models import CreditKind, SubmissionCredit
from apps.sampling.services import bulk_assign_cases

from .test_research_assistants import _call, _client, _submission, team, work  # noqa: F401  (fixtures)


def _found(team, work, *, kii=False):
    if kii:
        body = {"ra_id": team["rudo"].id, "kii_ids": [work["kii"].kii_id], "found": True}
        return _client(team["pi"]).post("/api/v1/ra/assign-kii/", body, format="json")
    body = {"ra_id": team["rudo"].id, "sample_ids": [work["other_main"].sample_id], "found": True}
    return _client(team["pi"]).post("/api/v1/ra/assign-main/", body, format="json")


def test_the_finder_is_credited_even_when_another_ra_called_last(team, work):
    assert _found(team, work).status_code == 200
    case = work["other_main"]  # Tino's case before Rudo was recorded as its finder
    _call(case, team["tino"], days_ago=1)
    s = _submission(case, uuid="found")
    s.qa_status = QAStatus.QA_PASSED
    s.save(update_fields=["qa_status"])
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert (c.ra, c.kind, c.amount_usd) == (team["rudo"], CreditKind.ASSISTED, Decimal("2.50"))
    assert "Found" in c.evidence


def test_a_kii_the_finder_completes_with_nobody_else_involved_is_theirs(team, work):
    assert _found(team, work, kii=True).status_code == 200
    record = work["kii"]
    record.status, record.qa_status = KIIStatus.COMPLETED, KIIQAStatus.QA_PASSED
    record.save(update_fields=["status", "qa_status"])
    credit.refresh()
    c = SubmissionCredit.objects.get(kii_record=record)
    assert (c.ra, c.kind, c.amount_usd) == (team["rudo"], CreditKind.ASSISTED, Decimal("2.50"))


def test_found_work_is_never_moved_to_anyone_else(team, work, settings):
    _found(team, work)
    _found(team, work, kii=True)
    pi = _client(team["pi"])
    case, record = work["other_main"], work["kii"]
    # Bulk move from Rudo, a named move, and an unassignment: all leave it with Rudo.
    assert case.sample_id not in pi.post("/api/v1/ra/assign-main/", {"ra_id": team["tino"].id, "from": team["rudo"].id},
                                         format="json").json()["sample_ids"]
    assert pi.post("/api/v1/ra/assign-main/", {"ra_id": team["tino"].id, "sample_ids": [case.sample_id]},
                   format="json").json()["count"] == 0
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": None, "kii_ids": [record.kii_id]}, format="json").json()["count"] == 0
    assert case.sample_id not in bulk_assign_cases(to_user=team["tino"], from_user=team["rudo"], user=team["pi"])
    settings.RA_NEW_LINK_ASSIGNEE = "tino"
    record.refresh_from_db()
    record.assigned_ra = None  # even unassigned, a link does not give it to the rotation
    record.save(update_fields=["assigned_ra"])
    assert assign_on_link(record) is False
    # Nor from the case's own page.
    resp = pi.patch(f"/api/v1/sample-cases/{case.sample_id}/", {"assigned_ra": team["tino"].id}, format="json")
    assert resp.status_code == 400 and "stays with them" in resp.content.decode()
    case.refresh_from_db()
    assert case.assigned_ra == team["rudo"]
    # Moving it to the finder is still allowed.
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": team["rudo"].id, "kii_ids": [record.kii_id]},
                   format="json").json()["count"] == 1


def test_only_the_pi_records_a_finder_for_named_records_and_it_is_audited(team, work):
    body = {"ra_id": team["rudo"].id, "kii_ids": [work["kii"].kii_id], "found": True}
    assert _client(team["fc"]).post("/api/v1/ra/assign-kii/", body, format="json").status_code == 403
    work["kii"].refresh_from_db()
    assert work["kii"].found_by is None and work["kii"].assigned_ra is None  # refused before anything moved
    pi = _client(team["pi"])
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": team["rudo"].id, "from_unassigned": True, "found": True},
                   format="json").status_code == 400
    assert pi.post("/api/v1/ra/assign-kii/", {"ra_id": None, "kii_ids": [work["kii"].kii_id], "found": True},
                   format="json").status_code == 400
    assert pi.post("/api/v1/ra/assign-kii/", body, format="json").status_code == 200
    detail = pi.get(f"/api/v1/kii/{work['kii'].pk}/").json()
    assert (detail["found_by"], detail["found_by_name"], detail["assigned_ra"]) == (team["rudo"].id, "Rudo", team["rudo"].id)
    assert AuditEvent.objects.filter(action="ra.finder_recorded").count() == 1
    # A PATCH cannot set it.
    pi.patch(f"/api/v1/kii/{work['kii'].pk}/", {"found_by": team["tino"].id}, format="json")
    work["kii"].refresh_from_db()
    assert work["kii"].found_by == team["rudo"]
    # The PI can clear it, which lets the record move again.
    assert pi.post("/api/v1/ra/assign-kii/", {**body, "found": False}, format="json").status_code == 200
    work["kii"].refresh_from_db()
    assert work["kii"].found_by is None
