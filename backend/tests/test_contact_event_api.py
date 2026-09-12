"""
Hardening pass: the admin "log a contact attempt" UI (sample case detail page)
posts to /api/v1/contacts/{sample_id}/events/ without a sample_case field --
the view resolves it from the URL. sample_case was left writable-and-required
on ContactEventSerializer, so is_valid() rejected every real caller with
"This field is required." before perform_create() ever got a chance to
inject it. Reproduced here before the fix (sample_case made read-only).
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import ContactChannel, ContactEvent, ContactOutcome


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="contact_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_log_contact_event_without_sample_case_in_body_succeeds(admin_client, main_case):
    resp = admin_client.post(
        f"/api/v1/contacts/{main_case.sample_id}/events/",
        {
            "channel": ContactChannel.PHONE,
            "occurred_at": "2026-09-11T10:00:00Z",
            "outcome": ContactOutcome.REACHED,
            "notes": "Reached the respondent.",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    event = ContactEvent.objects.get(sample_case=main_case)
    assert event.channel == ContactChannel.PHONE
    assert event.ra.username == "contact_admin"


def test_log_contact_event_ignores_client_supplied_sample_case(admin_client, main_case, locked_reserve_case):
    resp = admin_client.post(
        f"/api/v1/contacts/{main_case.sample_id}/events/",
        {
            "sample_case": locked_reserve_case.id,
            "channel": ContactChannel.EMAIL,
            "occurred_at": "2026-09-11T10:00:00Z",
            "outcome": ContactOutcome.NO_ANSWER,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    event = ContactEvent.objects.get(id=resp.data["id"])
    assert event.sample_case_id == main_case.id
