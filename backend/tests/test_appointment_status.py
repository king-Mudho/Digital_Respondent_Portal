"""
Hardening pass: Appointment.status is deliberately read-only on the public-
facing serializer, but that left no way for an RA to actually confirm or
complete an appointment -- adding the dedicated status endpoint here.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.contacts.models import Appointment, AppointmentMode, AppointmentStatus


@pytest.fixture
def admin_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="appt_admin", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def appointment(main_case):
    from django.utils import timezone

    return Appointment.objects.create(
        sample_case=main_case, scheduled_for=timezone.now(), mode=AppointmentMode.PHONE,
        status=AppointmentStatus.REQUESTED,
    )


def test_status_update_succeeds(admin_client, appointment):
    resp = admin_client.post(
        f"/api/v1/appointments/{appointment.id}/status/", {"status": AppointmentStatus.CONFIRMED}, format="json"
    )
    assert resp.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.CONFIRMED


def test_invalid_status_rejected(admin_client, appointment):
    resp = admin_client.post(f"/api/v1/appointments/{appointment.id}/status/", {"status": "NOT_A_STATUS"}, format="json")
    assert resp.status_code == 400
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.REQUESTED


def test_public_create_cannot_set_status_directly(main_case):
    from apps.invitations.services import issue_invitation

    raw_token, _, _ = issue_invitation(main_case)
    client = APIClient()
    resp = client.post("/api/v1/appointments/", {
        "token": raw_token,
        "scheduled_for": "2026-12-01T10:00:00Z",
        "mode": AppointmentMode.PHONE,
        "status": AppointmentStatus.COMPLETED,  # should be ignored
    }, format="json")
    assert resp.status_code == 201
    appt = Appointment.objects.get(sample_case=main_case)
    assert appt.status == AppointmentStatus.REQUESTED  # default, not attacker-supplied COMPLETED
