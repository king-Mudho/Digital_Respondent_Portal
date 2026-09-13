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


def _consented_token(main_case):
    """A valid token on a case that has given participation consent --
    the public appointment POST requires it (PI decision, Sep 2026)."""
    from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
    from apps.consent.services import record_consent
    from apps.invitations.services import issue_invitation

    raw_token, _, _ = issue_invitation(main_case)
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    return raw_token


def test_public_create_cannot_set_status_directly(main_case):
    raw_token = _consented_token(main_case)
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


def test_public_create_requires_participation_consent(main_case):
    """PI decision (Sep 2026): requesting a researcher call is a route into
    the same study, not a separate enquiry -- it records a named person's
    availability against an identified organisation and puts them on an
    RA's call list, so it sits behind the same consent gate as the
    self-administered route."""
    from apps.invitations.services import issue_invitation

    raw_token, _, _ = issue_invitation(main_case)
    client = APIClient()

    resp = client.post("/api/v1/appointments/", {
        "token": raw_token,
        "scheduled_for": "2026-12-01T10:00:00Z",
        "mode": AppointmentMode.PHONE,
    }, format="json")

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "consent_required"
    assert not Appointment.objects.filter(sample_case=main_case).exists()


def test_public_create_refused_after_consent_is_declined(main_case):
    from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
    from apps.consent.services import record_consent
    from apps.invitations.services import issue_invitation

    raw_token, _, _ = issue_invitation(main_case)
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.DECLINED,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    client = APIClient()

    resp = client.post("/api/v1/appointments/", {
        "token": raw_token,
        "scheduled_for": "2026-12-01T10:00:00Z",
        "mode": AppointmentMode.PHONE,
    }, format="json")

    assert resp.status_code == 403
    assert not Appointment.objects.filter(sample_case=main_case).exists()
