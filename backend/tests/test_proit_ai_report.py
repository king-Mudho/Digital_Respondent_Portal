"""manage.py proit_ai_report: a read-only summary for the ethics and methodology write-up."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.proit.management.commands.proit_ai_report import report
from apps.proit.models import AIProposal, AIResearchRun, AIResearchStatus, PreProfile


def _run_with(main_case, statuses):
    profile = PreProfile.objects.create(sample_case=main_case)
    run = AIResearchRun.objects.create(pre_profile=profile, status=AIResearchStatus.DONE, searches_used=10, tokens_in=1000, tokens_out=100)
    for i, st in enumerate(statuses):
        AIProposal.objects.create(run=run, pre_profile=profile, field_id=f"f{i}", status=st, confidence="HIGH" if st != "NOT_FOUND" else "")
    return run


@pytest.mark.django_db
def test_an_empty_system_reports_nothing_and_does_not_divide_by_zero():
    out = StringIO()
    call_command("proit_ai_report", stdout=out)
    assert "No proposal has been accepted or rejected yet." in out.getvalue()
    assert report()["accepted_share"] is None


@pytest.mark.django_db
def test_it_counts_what_researchers_accepted_edited_and_rejected(main_case):
    _run_with(main_case, ["ACCEPTED", "ACCEPTED", "EDITED", "REJECTED", "NOT_FOUND", "PROPOSED"])
    r = report()
    assert r["decided"] == 4 and r["accepted_share"] == 0.75  # 3 of the 4 decided were accepted
    assert r["edited_share_of_accepted"] == pytest.approx(1 / 3)
    assert r["searches"] == 10 and r["organisations_researched"] == 1
    out = StringIO()
    call_command("proit_ai_report", stdout=out)
    assert "accepted (with or without edits): 75%" in out.getvalue()


@pytest.mark.django_db
def test_it_never_changes_anything(main_case):
    _run_with(main_case, ["ACCEPTED", "REJECTED"])
    before = AIProposal.objects.count()
    call_command("proit_ai_report", stdout=StringIO())
    assert AIProposal.objects.count() == before
