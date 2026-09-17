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
    build_kii_coding_url,
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


# --- KII Guide: prefilled interview link ------------------------------------

def _consent(kii_record, consent_type):
    record_consent(
        kii_record=kii_record, consent_type=consent_type, decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0", method=ConsentMethod.VERBAL_RA_RECORDED,
    )


def test_coding_url_none_when_not_configured(kii_record, settings):
    settings.KOBO_KII_FORM_URL = ""
    _consent(kii_record, ConsentType.PARTICIPATION)
    assert build_kii_coding_url(kii_record) is None


def test_coding_url_none_before_participation_consent(kii_record, settings):
    """There is no legitimate reason to hand out a link to run the
    interview instrument on someone before they have consented to take
    part -- the gate this test protects."""
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"
    assert build_kii_coding_url(kii_record) is None


def test_coding_url_after_consent(kii_record, settings):
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"
    _consent(kii_record, ConsentType.PARTICIPATION)

    url = build_kii_coding_url(kii_record)

    assert url.startswith("https://ee.kobotoolbox.org/x/abcd1234?")
    assert f"d[part_a/KII_ID]={kii_record.kii_id}" in url


def test_coding_url_never_carries_participant_identity(kii_record, settings):
    """A KIIRecord identifies a real person -- unlike a DocumentRecord's
    title/author, participant_name/role/organisation must never appear in
    a URL handed to a third-party service or left in browser history."""
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"
    _consent(kii_record, ConsentType.PARTICIPATION)

    url = build_kii_coding_url(kii_record)

    assert "Moyo" not in url
    assert "SME" not in url
    assert "participant_name" not in url
    assert "participant_role" not in url


def test_coding_url_recording_consent_alone_is_not_enough(kii_record, settings):
    """Recording consent is a separate decision from participation consent
    (AGENTS.md ground rule 6) -- it must not accidentally satisfy this gate."""
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"
    _consent(kii_record, ConsentType.KII_RECORDING)
    assert build_kii_coding_url(kii_record) is None


def test_serializer_exposes_coding_state(qa_client, kii_record, settings):
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/abcd1234"

    not_consented = qa_client.get(f"/api/v1/kii/{kii_record.id}/")
    assert not_consented.data["kii_form_configured"] is True
    assert not_consented.data["coding_url"] is None

    _consent(kii_record, ConsentType.PARTICIPATION)
    consented = qa_client.get(f"/api/v1/kii/{kii_record.id}/")
    assert consented.data["coding_url"] is not None
