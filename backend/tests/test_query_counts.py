"""
Query counts that must not grow with the data (added 2026-09-15).

Measured before the fix: the Main-400 register ran 2 extra queries per row,
the KII register 1, the analysis export 1 per submission, and the Follow-ups
screen several per invited case. Each test builds a few rows, counts, then
builds many more and checks the count did not move.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent
from apps.invitations.services import issue_invitation
from apps.kii.models import KIIRecord
from apps.kobo.models import QUANSubmission
from apps.sampling.models import SampleType
from apps.sampling.services import create_sample_case, transition_workflow_status


def _pi():
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="qc_pi", password="x", role=role))
    return client


def _count(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
        if hasattr(response, "streaming_content"):
            b"".join(response.streaming_content)
    assert response.status_code == 200, url
    return len(ctx.captured_queries)


def _cases(organisation, stratum, n):
    return [create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
            for _ in range(n)]


@pytest.mark.django_db
def test_register_queries_do_not_grow_with_rows(organisation, stratum):
    client = _pi()
    _cases(organisation, stratum, 3)
    few = _count(client, "/api/v1/sample-cases/?sample_type=MAIN")
    _cases(organisation, stratum, 15)
    assert _count(client, "/api/v1/sample-cases/?sample_type=MAIN") == few


@pytest.mark.django_db
def test_kii_register_queries_do_not_grow_with_rows():
    client = _pi()
    for i in range(3):
        KIIRecord.objects.create(kii_id=f"KII-{i:04d}", participant_name=f"P{i}")
    few = _count(client, "/api/v1/kii/")
    for i in range(3, 18):
        KIIRecord.objects.create(kii_id=f"KII-{i:04d}", participant_name=f"P{i}")
    assert _count(client, "/api/v1/kii/") == few


def _invited(case, days_ago):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    Respondent.objects.create(sample_case=case, full_name="R", is_eligible=True, whatsapp_number="0771234567")
    _, _, token = issue_invitation(case)
    token.issued_at = timezone.now() - timedelta(days=days_ago)
    token.save(update_fields=["issued_at"])


@pytest.mark.django_db
def test_follow_ups_queries_do_not_grow_with_invited_cases(organisation, stratum):
    client = _pi()
    for case in _cases(organisation, stratum, 2):
        _invited(case, 3)
    few = _count(client, "/api/v1/follow-ups/")
    for case in _cases(organisation, stratum, 12):
        _invited(case, 3)
    assert len(client.get("/api/v1/follow-ups/").json()["results"]) == 14
    assert _count(client, "/api/v1/follow-ups/") == few


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/v1/export/analysis/", "/api/v1/export/operational/"])
def test_exports_do_not_query_per_submission(organisation, stratum, url):
    client = _pi()

    def submit(cases):
        for case in cases:
            Respondent.objects.create(sample_case=case, full_name="R", phone="0770000000")
            QUANSubmission.objects.create(sample_case=case, kobo_submission_uuid=f"qc-{case.id}",
                                          administration_mode="01", submitted_at=timezone.now())

    submit(_cases(organisation, stratum, 2))
    few = _count(client, url)
    submit(_cases(organisation, stratum, 10))
    assert _count(client, url) == few
