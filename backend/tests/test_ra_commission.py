"""Research assistants earn a commission per completion credited to them (PI, 23 Nov 2026): US$2.50 by default,
settings.RA_COMMISSION_USD. Under test:

- an administered or assisted completion earns the rate; one with no RA earns nothing;
- a questionnaire or a KII earns only once it has passed QA (PI, 23 Nov 2026): nothing while pending or queried,
  nothing if rejected, and the rate when it passes; the PI passes a KII on its own page;
- each credit keeps the amount it was first credited at, so changing the rate pays new completions only;
- the PI's override moves the amount with the credit, and taking a credit away takes its amount away;
- My work shows an RA their own total and nobody else's; the team screen and pay sheet show every RA's.
"""

from decimal import Decimal

import pytest

from apps.kii.models import KIIStatus
from apps.kobo.models import QAStatus
from apps.ra import credit
from apps.ra.models import SubmissionCredit

from .test_research_assistants import _call, _client, team, work  # noqa: F401  (fixtures)
from .test_research_assistants import _submission as _pending_submission


def _submission(case, *, qa=QAStatus.QA_PASSED, **kwargs):
    s = _pending_submission(case, **kwargs)
    s.qa_status = qa
    s.save(update_fields=["qa_status"])
    return s


def _qa(submission, status):
    submission.qa_status = status
    submission.save(update_fields=["qa_status"])


@pytest.fixture(autouse=True)
def _rate(settings):
    settings.RA_COMMISSION_USD = 2.50


def test_a_credited_completion_earns_the_rate_and_an_uncredited_one_nothing(team, work):
    _submission(work["main"], ra=team["rudo"], uuid="adm")
    _call(work["other_main"], team["pi"], days_ago=1)  # the PI's own call credits nobody
    _submission(work["other_main"], uuid="none")
    credit.refresh()
    amounts = {c.quan_submission.kobo_submission_uuid: c.amount_usd for c in SubmissionCredit.objects.all()}
    assert amounts == {"adm": Decimal("2.50"), "none": Decimal("0.00")}


def test_an_assisted_completion_earns_the_same_as_an_administered_one(team, work):
    _call(work["main"], team["rudo"], days_ago=2)
    _submission(work["main"], days_ago=1, uuid="ast")
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert (c.ra, c.amount_usd) == (team["rudo"], Decimal("2.50"))


def test_changing_the_rate_pays_new_completions_only(team, work, settings):
    _submission(work["main"], ra=team["rudo"], uuid="old")
    credit.refresh()
    settings.RA_COMMISSION_USD = 3.00
    _submission(work["other_main"], ra=team["rudo"], uuid="new")
    credit.refresh()
    amounts = {c.quan_submission.kobo_submission_uuid: c.amount_usd for c in SubmissionCredit.objects.all()}
    assert amounts == {"old": Decimal("2.50"), "new": Decimal("3.00")}
    assert credit.refresh() == {"created": 0, "updated": 0}  # still idempotent


def test_a_questionnaire_earns_only_once_it_passes_qa(team, work):
    s = _submission(work["main"], ra=team["rudo"], uuid="q", qa=QAStatus.PENDING)
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert (c.ra, c.amount_usd) == (team["rudo"], Decimal("0.00"))  # credited, not yet paid
    mine = _client(team["rudo"]).get("/api/v1/ra/my-work/").json()
    assert (mine["totals"]["earned_usd"], mine["totals"]["awaiting_qa"]) == (0.0, 1)
    _qa(s, QAStatus.QUERY)
    credit.refresh()
    c.refresh_from_db()
    assert c.amount_usd == Decimal("0.00")
    _qa(s, QAStatus.QA_PASSED)
    credit.refresh()
    c.refresh_from_db()
    assert c.amount_usd == Decimal("2.50")
    mine = _client(team["rudo"]).get("/api/v1/ra/my-work/").json()
    assert (mine["totals"]["earned_usd"], mine["totals"]["awaiting_qa"]) == (2.5, 0)


def test_a_rejected_questionnaire_earns_nothing(team, work):
    s = _submission(work["main"], ra=team["rudo"], uuid="q")
    credit.refresh()
    assert SubmissionCredit.objects.get().amount_usd == Decimal("2.50")
    _qa(s, QAStatus.REJECTED)  # QA reverses its decision
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert (c.ra, c.amount_usd) == (team["rudo"], Decimal("0.00"))


def test_a_kii_earns_only_once_the_pi_passes_its_qa(team, work):
    record = work["kii"]
    record.interviewer, record.status = team["rudo"], KIIStatus.COMPLETED
    record.save(update_fields=["interviewer", "status"])
    credit.refresh()
    c = SubmissionCredit.objects.get(kii_record=record)
    assert (c.ra, c.amount_usd) == (team["rudo"], Decimal("0.00"))  # completed, QA pending
    assert _client(team["rudo"]).get("/api/v1/ra/my-work/").json()["totals"]["awaiting_qa"] == 1
    url = f"/api/v1/kii/{record.pk}/qa/"
    assert _client(team["pi"]).post(url, {"qa_status": "QA_PASSED"}, format="json").status_code == 200
    credit.refresh()
    c.refresh_from_db()
    assert c.amount_usd == Decimal("2.50")
    assert _client(team["pi"]).post(url, {"qa_status": "REJECTED", "note": "Recording is of a different person"},
                                    format="json").status_code == 200
    credit.refresh()
    c.refresh_from_db()
    assert c.amount_usd == Decimal("0.00")


def test_an_overridden_questionnaire_is_still_paid_only_after_qa(team, work):
    s = _pending_submission(work["main"], days_ago=1)  # pending QA, no RA
    credit.refresh()
    c = SubmissionCredit.objects.get()
    credit.override(c, ra=team["rudo"], kind="ASSISTED", reason="Phoned from her own phone", user=team["pi"])
    c.refresh_from_db()
    assert c.amount_usd == Decimal("0.00")
    _qa(s, QAStatus.QA_PASSED)
    credit.refresh()
    c.refresh_from_db()
    assert (c.ra, c.amount_usd) == (team["rudo"], Decimal("2.50"))


def test_an_override_moves_the_amount_with_the_credit(team, work):
    _submission(work["main"], days_ago=1)  # QA-passed, no RA
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert c.amount_usd == Decimal("0.00")
    credit.override(c, ra=team["rudo"], kind="ASSISTED", reason="Phoned from her own phone", user=team["pi"])
    c.refresh_from_db()
    assert c.amount_usd == Decimal("2.50")
    credit.override(c, ra=None, kind="UNCREDITED", reason="Respondent did it alone after all", user=team["pi"])
    c.refresh_from_db()
    assert c.amount_usd == Decimal("0.00")


def test_my_work_shows_my_earnings_and_the_team_screen_everyones(team, work):
    _submission(work["main"], ra=team["rudo"], uuid="r1")
    _submission(work["other_main"], ra=team["tino"], uuid="t1")
    mine = _client(team["rudo"]).get("/api/v1/ra/my-work/").json()
    assert mine["commission_usd"] == 2.5
    assert mine["totals"]["earned_usd"] == 2.5
    assert [c["amount_usd"] for c in mine["credits"]] == [2.5]  # only Rudo's own
    sheet = _client(team["pi"]).get("/api/v1/ra/team/").json()
    assert {t["username"]: t["credits"]["earned_usd"] for t in sheet["team"]} == {"rudo": 2.5, "tino": 2.5}
    assert sheet["earned_usd"] == 5.0
    csv_text = _client(team["pi"]).get("/api/v1/ra/team/", {"download": "csv"}).content.decode()
    assert "Commission (US$)" in csv_text.splitlines()[0] and csv_text.count(",2.50") == 2
    # Another RA's money is never on an RA's own page.
    assert _client(team["rudo"]).get("/api/v1/ra/team/").status_code == 403
