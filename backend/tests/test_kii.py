"""
KII status flow and the separate participation/recording consent rule
(AGENTS.md ground rule 6, docs/13_KII_MODULE.md).
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.kii.models import KIIStatus
from apps.kii.services import (
    InvalidKIITransition,
    KIIRecordingConsentRequired,
    create_kii_record,
    mark_completed,
    transition_kii_status,
)


@pytest.fixture
def kii_record(db):
    return create_kii_record(
        stakeholder_category="Financial institution representative",
        participant_name="Dr. T. Moyo",
        participant_role="Head of SME Lending",
        preferred_mode="PHONE",
    )


def test_kii_id_format(kii_record):
    import re

    assert re.fullmatch(r"KII-\d{4}", kii_record.kii_id)


def test_valid_status_transition(kii_record):
    updated = transition_kii_status(kii_record, KIIStatus.SCHEDULED)
    assert updated.status == KIIStatus.SCHEDULED


def test_invalid_status_transition_rejected(kii_record):
    with pytest.raises(InvalidKIITransition):
        transition_kii_status(kii_record, KIIStatus.COMPLETED)  # can't skip SCHEDULED


def test_completed_without_recording_needs_no_consent(kii_record):
    transition_kii_status(kii_record, KIIStatus.SCHEDULED)
    updated = mark_completed(kii_record, with_recording=False)
    assert updated.status == KIIStatus.COMPLETED


def test_completed_with_recording_requires_recording_consent(kii_record):
    transition_kii_status(kii_record, KIIStatus.SCHEDULED)
    with pytest.raises(KIIRecordingConsentRequired):
        mark_completed(kii_record, with_recording=True)


def test_participation_consent_never_implies_recording_consent(kii_record):
    """The exact rule AGENTS.md ground rule 6 exists to enforce."""
    transition_kii_status(kii_record, KIIStatus.SCHEDULED)
    record_consent(
        kii_record=kii_record,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.VERBAL_RA_RECORDED,
    )
    with pytest.raises(KIIRecordingConsentRequired):
        mark_completed(kii_record, with_recording=True)


def test_completed_with_recording_succeeds_after_separate_recording_consent(kii_record):
    transition_kii_status(kii_record, KIIStatus.SCHEDULED)
    record_consent(
        kii_record=kii_record,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.VERBAL_RA_RECORDED,
    )
    record_consent(
        kii_record=kii_record,
        consent_type=ConsentType.KII_RECORDING,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.VERBAL_RA_RECORDED,
    )
    updated = mark_completed(kii_record, with_recording=True)
    assert updated.status == KIIStatus.COMPLETED


@pytest.fixture
def qa_client(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    user = User.objects.create_user(username="kii_qa", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_serializer_exposes_no_consent_recorded_by_default(qa_client, kii_record):
    resp = qa_client.get(f"/api/v1/kii/{kii_record.id}/")
    assert resp.status_code == 200
    assert resp.data["participation_consent_decision"] is None
    assert resp.data["recording_consent_decision"] is None


def test_serializer_reflects_recorded_consent_decision(qa_client, kii_record):
    """The admin KII detail page has no other way to show an RA that
    participation/recording consent was already captured for this KII --
    without this field it silently offered no feedback after clicking
    "Record participation consent" (hardening pass, Sep 2026)."""
    qa_client.post(
        f"/api/v1/kii/{kii_record.id}/consent/",
        {"consent_type": ConsentType.PARTICIPATION, "decision": ConsentDecision.GIVEN,
         "information_sheet_version": "v1.0", "method": ConsentMethod.VERBAL_RA_RECORDED},
        format="json",
    )
    resp = qa_client.get(f"/api/v1/kii/{kii_record.id}/")
    assert resp.data["participation_consent_decision"] == ConsentDecision.GIVEN
    assert resp.data["recording_consent_decision"] is None
