"""
End-to-end audit pass: the register screens were unusable at real data
volumes. PAGE_SIZE is 20 against 400 Main + 400 Reserve cases, 90 KII
records and 100 documents, and there was no search, no page control, and
-- for KII and documents -- no deterministic ordering behind the pages.

These tests pin the API side of that fix: ?search= narrows each register,
and paging over an unordered queryset can no longer silently repeat or
drop rows. The appointment queue's identifying fields are covered here too,
since the queue showed only numeric FKs and an RA could not tell whose
appointment a row was.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Appointment, AppointmentMode, AppointmentStatus
from apps.evidence.models import DocumentRecord, DocumentType
from apps.kii.models import KIIRecord
from apps.sampling.models import ActorFamily, Province, SampleType, SizeClass
from apps.sampling.services import create_organisation, create_sample_case


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="register_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def many_cases(db, stratum):
    """More cases than one page holds, with distinguishable names."""
    cases = []
    for i in range(25):
        organisation = create_organisation(
            province=Province.HARARE,
            name=f"Findable Cooperative {i:02d}" if i == 7 else f"Bulk Organisation {i:02d}",
            entity_type="Private Limited Company",
            district="Harare",
            actor_family=ActorFamily.PRODUCER_PRIMARY,
            value_chain="Horticulture",
            size_class=SizeClass.SME,
        )
        cases.append(
            create_sample_case(
                organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026
            )
        )
    return cases


def test_sample_register_pages_beyond_the_first_page(admin_client, many_cases):
    page_one = admin_client.get("/api/v1/sample-cases/?sample_type=MAIN").json()
    page_two = admin_client.get("/api/v1/sample-cases/?sample_type=MAIN&page=2").json()

    assert page_one["count"] == 25
    assert len(page_one["results"]) == 20
    assert len(page_two["results"]) == 5

    # No row may appear on both pages, and every row must appear on one.
    seen = [row["sample_id"] for row in page_one["results"] + page_two["results"]]
    assert len(set(seen)) == 25


def test_sample_register_search_narrows_to_the_matching_case(admin_client, many_cases):
    response = admin_client.get("/api/v1/sample-cases/?search=Findable")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["organisation_name"] == "Findable Cooperative 07"


def test_sample_register_search_matches_the_sample_id_too(admin_client, many_cases):
    target = many_cases[3].sample_id

    body = admin_client.get(f"/api/v1/sample-cases/?search={target}").json()

    assert [row["sample_id"] for row in body["results"]] == [target]


def test_organisation_register_search(admin_client, many_cases):
    body = admin_client.get("/api/v1/organisations/?search=Findable").json()

    assert body["count"] == 1
    assert body["results"][0]["name"] == "Findable Cooperative 07"


@pytest.mark.django_db
def test_kii_register_paging_is_deterministic(admin_client):
    # Inserted in reverse so an unordered queryset (which Postgres tends to
    # return in insertion order for a small table) fails the sorted
    # assertion below rather than passing by luck.
    for i in reversed(range(25)):
        KIIRecord.objects.create(
            kii_id=f"KII-{i:04d}",
            stakeholder_category="Regulator",
            participant_name=f"Informant {i:02d}",
            participant_role="Director",
        )

    page_one = admin_client.get("/api/v1/kii/").json()
    page_two = admin_client.get("/api/v1/kii/?page=2").json()
    seen = [row["kii_id"] for row in page_one["results"] + page_two["results"]]

    assert page_one["count"] == 25
    assert len(set(seen)) == 25, "a record appeared on two pages -- queryset is unordered"
    assert seen == sorted(seen)


@pytest.mark.django_db
def test_kii_register_search(admin_client):
    KIIRecord.objects.create(
        kii_id="KII-9001", stakeholder_category="Regulator",
        participant_name="Tendai Moyo", participant_role="Director",
    )
    KIIRecord.objects.create(
        kii_id="KII-9002", stakeholder_category="Financier",
        participant_name="Rudo Chikwava", participant_role="Analyst",
    )

    body = admin_client.get("/api/v1/kii/?search=Rudo").json()

    assert [row["kii_id"] for row in body["results"]] == ["KII-9002"]


@pytest.mark.django_db
def test_document_register_paging_is_deterministic(admin_client):
    # Reverse insertion order, same reason as the KII test above.
    for i in reversed(range(25)):
        DocumentRecord.objects.create(
            document_id=f"DOC-{i:04d}", title=f"Bulk document {i:02d}",
            document_type=DocumentType.OFFICIAL,
        )

    page_one = admin_client.get("/api/v1/documents/").json()
    page_two = admin_client.get("/api/v1/documents/?page=2").json()
    seen = [row["document_id"] for row in page_one["results"] + page_two["results"]]

    assert page_one["count"] == 25
    assert len(set(seen)) == 25, "a document appeared on two pages -- queryset is unordered"
    assert seen == sorted(seen)


@pytest.mark.django_db
def test_document_register_search(admin_client):
    DocumentRecord.objects.create(
        document_id="DOC-9001", title="National Horticulture Strategy",
        document_type=DocumentType.OFFICIAL,
    )
    DocumentRecord.objects.create(
        document_id="DOC-9002", title="Seed Import Circular",
        document_type=DocumentType.OFFICIAL,
    )

    body = admin_client.get("/api/v1/documents/?search=Horticulture").json()

    assert [row["document_id"] for row in body["results"]] == ["DOC-9001"]


def test_appointment_queue_identifies_the_case(admin_client, main_case):
    Appointment.objects.create(
        sample_case=main_case, scheduled_for=timezone.now(),
        mode=AppointmentMode.PHONE, status=AppointmentStatus.REQUESTED,
    )

    row = admin_client.get("/api/v1/appointments/").json()["results"][0]

    assert row["sample_id"] == main_case.sample_id
    assert row["organisation_name"] == main_case.organisation.name
    assert row["kii_id"] is None


@pytest.mark.django_db
def test_appointment_queue_handles_a_kii_appointment(admin_client):
    """Both FKs are nullable -- a KII appointment has no sample case, and
    the serializer must not blow up reaching through the null one."""
    record = KIIRecord.objects.create(
        kii_id="KII-9100", stakeholder_category="Regulator",
        participant_name="Tendai Moyo", participant_role="Director",
    )
    Appointment.objects.create(
        kii_record=record, scheduled_for=timezone.now(),
        mode=AppointmentMode.PHONE, status=AppointmentStatus.REQUESTED,
    )

    row = admin_client.get("/api/v1/appointments/").json()["results"][0]

    assert row["kii_id"] == "KII-9100"
    assert row["sample_id"] is None
    assert row["organisation_name"] is None
