"""Reports screen analytics (added 2026-09-15)."""

import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.services import record_eligibility_check
from apps.invitations.services import issue_invitation, validate_token
from apps.kobo.models import QAStatus, QUANSubmission


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _stage(report, stage):
    return next(item["cases"] for item in report["funnel"] if item["stage"] == stage)


@pytest.mark.django_db
def test_the_funnel_counts_each_case_once_at_its_furthest_stage(main_case):
    raw, _, _ = issue_invitation(main_case)
    validate_token(raw)
    issue_invitation(main_case, invitation_wave=2)  # a reissue must not double-count
    record_eligibility_check(sample_case=main_case, full_name="Tendai Moyo", role_category="CEO_MD", is_eligible=True)
    record_consent(sample_case=main_case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
                   information_sheet_version="v1.3", method=ConsentMethod.WEB_CLICKTHROUGH)
    QUANSubmission.objects.create(
        sample_case=main_case, kobo_submission_uuid="r-1", administration_mode="01",
        submitted_at=timezone.now() - timedelta(days=1), completion_seconds=17 * 60, qa_status=QAStatus.QA_PASSED,
    )

    report = _client(Role.ANALYST, "rp_an").get("/api/v1/reports/overview/?range=30").json()

    assert [_stage(report, s) for s in ("invited", "opened", "eligible", "consented", "started", "submitted", "qa_passed")] \
        == [1, 1, 1, 1, 1, 1, 1]
    assert report["kpis"]["response_rate"] == 1.0
    assert report["kpis"]["median_completion_minutes"] == 17
    assert next(b for b in report["duration_histogram"] if b["bucket"] == "15–20")["submissions"] == 1
    assert sum(day["submissions"] for day in report["submissions_by_day"]) == 1
    assert len(report["submissions_by_day"]) == 30
    [province] = report["breakdowns"]["province"]
    assert (province["cases"], province["invited"], province["submitted"]) == (1, 1, 1)


@pytest.mark.django_db
def test_the_report_names_no_organisation_or_person(main_case):
    record_eligibility_check(sample_case=main_case, full_name="Tendai Moyo", role_category="CEO_MD", is_eligible=True)
    body = json.dumps(_client(Role.PI_ADMIN, "rp_pi").get("/api/v1/reports/overview/?range=all").json())
    assert main_case.organisation.name not in body
    assert "Tendai" not in body
    assert main_case.sample_id not in body and main_case.organisation.master_id not in body


@pytest.mark.django_db
def test_report_access_follows_the_dashboard_roles():
    for role, allowed in [(Role.PI_ADMIN, True), (Role.FIELD_COORDINATOR, True), (Role.ANALYST, True),
                          (Role.SUPERVISOR_READONLY, True), (Role.CONTACT_RA, False), (Role.KII_RA, False)]:
        status = _client(role, f"rp_{role.lower()}").get("/api/v1/reports/overview/").status_code
        assert (status == 200) is allowed, role


@pytest.mark.django_db
def test_an_unknown_range_falls_back_to_thirty_days():
    report = _client(Role.ANALYST, "rp_range").get("/api/v1/reports/overview/?range=forever").json()
    assert report["range"]["key"] == "30" and len(report["submissions_by_day"]) == 30


@pytest.mark.django_db
def test_a_dominant_administration_mode_raises_the_imbalance_alert(organisation, stratum):
    from apps.qa.services import seed_default_thresholds
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_sample_case

    seed_default_thresholds()
    for i in range(10):
        case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
        QUANSubmission.objects.create(sample_case=case, kobo_submission_uuid=f"mi-{i}", submitted_at=timezone.now(),
                                      administration_mode="01" if i < 9 else "03")
    imbalance = _client(Role.PI_ADMIN, "rp_mi").get("/api/v1/reports/overview/?range=30").json()["mode_imbalance"]
    assert (imbalance["alert"], imbalance["share"], imbalance["threshold"]) == (True, 0.9, 0.7)
