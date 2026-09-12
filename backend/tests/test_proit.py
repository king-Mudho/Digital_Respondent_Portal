"""
PROIT (ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx): a pre-interview
desk-research/verification layer. These tests exercise the document's own
"non-negotiable deployment rules" directly -- the field-ID whitelist (never
a frozen core construct item), no value without provenance, human review
before lock, immutability after lock, and that a respondent's correction
never overwrites the documentary record.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.proit.models import (
    Confidence,
    GapClassification,
    PreProfile,
    VerificationStatusCode,
)
from apps.proit.services import (
    PreProfileError,
    PreProfileLocked,
    PreProfileNotLocked,
    add_evidence,
    add_field,
    compute_burden_metrics,
    compute_field_confidence,
    create_pre_profile,
    field_is_displayable,
    lock_pre_profile,
    reconcile_field,
    record_verification,
    render_probe_template,
)


@pytest.fixture
def admin_user(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    return User.objects.create_user(username="proit_admin", password="testpass123", role=role)


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


def test_pre_profile_requires_exactly_one_of_sample_case_or_kii_record(main_case):
    from apps.kii.services import create_kii_record

    with pytest.raises(ValidationError):
        create_pre_profile()  # neither set

    kii_record = create_kii_record(
        stakeholder_category="Government, regulator & parastatal",
        participant_name="Test Officeholder", participant_role="Director",
    )
    with pytest.raises(ValidationError):
        profile = PreProfile(sample_case=main_case, kii_record=kii_record)
        profile.full_clean()  # both set

    # valid: exactly one
    profile = create_pre_profile(sample_case=main_case)
    assert profile.sample_case_id == main_case.id


def test_add_field_rejects_field_id_outside_the_catalog(main_case):
    profile = create_pre_profile(sample_case=main_case)
    with pytest.raises(KeyError):
        add_field(profile, "abi_core_score")  # a frozen construct item, never in the catalog


def test_add_field_accepts_a_cataloged_field(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    assert field.module == "ORGANISATION_PROFILE"
    assert field.route == "BOTH"


def test_lock_rejects_a_documentary_value_with_no_evidence_source(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    with pytest.raises(PreProfileError):
        lock_pre_profile(profile, reviewer=admin_user)


def test_lock_succeeds_once_every_documentary_value_has_a_source(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(
        field, source_title="PRAZ registry entry", source_confidence=Confidence.HIGH,
        source_authority="TIER_1_STATUTORY",
    )
    locked = lock_pre_profile(profile, reviewer=admin_user)
    assert locked.prepopulation_locked_at is not None
    assert locked.researcher_reviewed is True
    assert locked.qa_reviewer_id == admin_user.id


def test_lock_is_not_reversible_through_the_service_layer(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    lock_pre_profile(profile, reviewer=admin_user)
    with pytest.raises(PreProfileLocked):
        lock_pre_profile(profile, reviewer=admin_user)


def test_cannot_add_evidence_after_lock(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry entry", source_confidence=Confidence.HIGH)
    lock_pre_profile(profile, reviewer=admin_user)
    with pytest.raises(PreProfileLocked):
        add_evidence(field, source_title="A second source", source_confidence=Confidence.HIGH)


def test_cannot_add_a_field_after_lock(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    lock_pre_profile(profile, reviewer=admin_user)
    with pytest.raises(PreProfileLocked):
        add_field(profile, "legal_name", documentary_value="Farmingville Investments")


# --- Confidence and gap-classification rules (document Section 4) ----------

def test_single_tier1_high_source_gives_high_confidence(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry", source_confidence=Confidence.HIGH, source_authority="TIER_1_STATUTORY")
    field.refresh_from_db()
    assert field.confidence == Confidence.HIGH


def test_two_concordant_credible_sources_give_high_confidence(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "year_established", documentary_value="2015")
    add_evidence(field, source_title="Official website", source_confidence=Confidence.MODERATE, source_authority="TIER_2_INSTITUTIONAL")
    add_evidence(field, source_title="Annual report", source_confidence=Confidence.MODERATE, source_authority="TIER_2_INSTITUTIONAL")
    field.refresh_from_db()
    assert field.confidence == Confidence.HIGH


def test_one_credible_source_gives_moderate_confidence(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "year_established", documentary_value="2015")
    add_evidence(field, source_title="Official website", source_confidence=Confidence.MODERATE, source_authority="TIER_2_INSTITUTIONAL")
    field.refresh_from_db()
    assert field.confidence == Confidence.MODERATE


def test_no_evidence_gives_low_confidence(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "year_established", documentary_value="2015")
    assert compute_field_confidence(field) == Confidence.LOW


def test_low_confidence_field_is_not_displayable_to_a_respondent(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "year_established", documentary_value="2015")
    # No evidence at all -> LOW confidence, never shown as a fact (ASK FULL instead).
    field.confidence = Confidence.LOW
    field.save(update_fields=["confidence"])
    assert field_is_displayable(field) is False


def test_high_confidence_field_is_displayable(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry", source_confidence=Confidence.HIGH, source_authority="TIER_1_STATUTORY")
    field.refresh_from_db()
    assert field_is_displayable(field) is True


def test_lock_classifies_conflicting_evidence_as_verify_and_probe(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "year_established", documentary_value="2015 or 2016")
    add_evidence(field, source_title="Source A", source_confidence=Confidence.MODERATE, source_conflict=True)
    add_evidence(field, source_title="Source B", source_confidence=Confidence.MODERATE, source_conflict=True)
    lock_pre_profile(profile, reviewer=admin_user)
    field.refresh_from_db()
    assert field.gap_classification == GapClassification.VERIFY_AND_PROBE


def test_lock_classifies_field_with_no_documentary_value_as_ask_full(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "digital_platforms")  # no documentary_value supplied
    lock_pre_profile(profile, reviewer=admin_user)
    field.refresh_from_db()
    assert field.gap_classification == GapClassification.ASK_FULL


# --- Respondent verification only after lock, and never erases the ---------
# --- documentary value (document's own non-negotiable rules) ---------------

def test_verification_is_rejected_before_lock(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    with pytest.raises(PreProfileNotLocked):
        record_verification(field, status=VerificationStatusCode.YES_CORRECT)


def test_respondent_correction_never_overwrites_the_documentary_value(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry", source_confidence=Confidence.HIGH)
    lock_pre_profile(profile, reviewer=admin_user)

    record_verification(
        field, status=VerificationStatusCode.NO_CORRECT_VALUE_PROVIDED,
        respondent_value="Farmingville Investments (Pvt) Ltd", comment="Legal suffix was missing.",
    )
    field.refresh_from_db()
    assert field.preliminary_documentary_value == "Farmingville Investments"
    assert field.respondent_value == "Farmingville Investments (Pvt) Ltd"


def test_reconciled_value_is_independent_of_the_other_two(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry", source_confidence=Confidence.HIGH)
    lock_pre_profile(profile, reviewer=admin_user)
    record_verification(field, status=VerificationStatusCode.NO_CORRECT_VALUE_PROVIDED, respondent_value="Farmingville Investments (Pvt) Ltd")

    reconcile_field(field, reconciled_value="Farmingville Investments (Private) Limited")
    field.refresh_from_db()
    assert field.preliminary_documentary_value == "Farmingville Investments"
    assert field.respondent_value == "Farmingville Investments (Pvt) Ltd"
    assert field.reconciled_value == "Farmingville Investments (Private) Limited"


def test_burden_reduction_score_formula(main_case, admin_user):
    profile = create_pre_profile(sample_case=main_case)
    verified_field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(verified_field, source_title="PRAZ registry", source_confidence=Confidence.HIGH)
    add_field(profile, "digital_platforms")  # no evidence -> ASK_FULL, not avoided
    lock_pre_profile(profile, reviewer=admin_user)
    compute_burden_metrics(profile)
    profile.refresh_from_db()
    assert profile.background_questions_avoided == 1
    assert profile.burden_reduction_score == 50.0


def test_probe_template_renders_with_evidence_substituted():
    text = render_probe_template("FINANCE_LENDER", evidence="a working capital facility")
    assert "a working capital facility" in text


def test_unknown_probe_template_role_raises():
    with pytest.raises(PreProfileError):
        render_probe_template("NOT_A_REAL_ROLE")


# --- API: permissions and the ethics/change-control gate --------------------

def test_contact_ra_cannot_manage_pre_profiles(main_case):
    role, _ = Role.objects.get_or_create(name=Role.CONTACT_RA)
    user = User.objects.create_user(username="proit_contact_ra", password="testpass123", role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post("/api/v1/proit/pre-profiles/", {"sample_case": main_case.id}, format="json")
    assert resp.status_code == 403


def test_field_coordinator_can_create_and_lock_a_pre_profile(admin_client, main_case):
    resp = admin_client.post("/api/v1/proit/pre-profiles/", {"sample_case": main_case.id}, format="json")
    assert resp.status_code == 201, resp.data
    pre_profile_id = resp.data["id"]

    field_resp = admin_client.post(
        f"/api/v1/proit/pre-profiles/{pre_profile_id}/fields/",
        {"field_id": "legal_name", "preliminary_documentary_value": "Farmingville Investments"},
        format="json",
    )
    assert field_resp.status_code == 201, field_resp.data
    field_id = field_resp.data["id"]

    evidence_resp = admin_client.post(
        f"/api/v1/proit/fields/{field_id}/evidence/",
        {"source_title": "PRAZ registry", "source_confidence": "HIGH"},
        format="json",
    )
    assert evidence_resp.status_code == 201, evidence_resp.data

    lock_resp = admin_client.post(f"/api/v1/proit/pre-profiles/{pre_profile_id}/lock/")
    assert lock_resp.status_code == 200, lock_resp.data
    assert lock_resp.data["prepopulation_locked_at"] is not None


def test_field_catalog_endpoint_never_lists_a_core_construct_item(admin_client):
    resp = admin_client.get("/api/v1/proit/field-catalog/")
    assert resp.status_code == 200
    assert "abi_core_score" not in resp.data
    assert "legal_name" in resp.data


@override_settings(PROIT_ENABLED_FOR_RESPONDENTS=False)
def test_respondent_profile_returns_null_when_disabled(main_case):
    from apps.invitations.services import issue_invitation

    raw_token, _, _ = issue_invitation(main_case)
    client = APIClient()
    resp = client.get(f"/api/v1/proit/respondent-profile/?t={raw_token}")
    assert resp.status_code == 200
    assert resp.data is None


@override_settings(PROIT_ENABLED_FOR_RESPONDENTS=True)
def test_respondent_profile_returns_only_displayable_fields_when_enabled(main_case, admin_user):
    from apps.invitations.services import issue_invitation

    profile = create_pre_profile(sample_case=main_case)
    high_field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(high_field, source_title="PRAZ registry", source_confidence=Confidence.HIGH, source_authority="TIER_1_STATUTORY")
    add_field(profile, "digital_platforms")  # no evidence -> LOW confidence, must not appear
    lock_pre_profile(profile, reviewer=admin_user)

    raw_token, _, _ = issue_invitation(main_case)
    client = APIClient()
    resp = client.get(f"/api/v1/proit/respondent-profile/?t={raw_token}")
    assert resp.status_code == 200
    field_ids = [f["field_id"] for f in resp.data["fields"]]
    assert field_ids == ["legal_name"]
    # Never expose source-internal notes to the respondent.
    assert "sources" not in resp.data["fields"][0]


@override_settings(PROIT_ENABLED_FOR_RESPONDENTS=True)
def test_respondent_can_verify_only_a_field_from_their_own_case(main_case, admin_user):
    from apps.invitations.services import issue_invitation
    from apps.sampling.services import create_organisation, create_sample_case

    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="Farmingville Investments")
    add_evidence(field, source_title="PRAZ registry", source_confidence=Confidence.HIGH)
    lock_pre_profile(profile, reviewer=admin_user)

    other_org = create_organisation(
        province=main_case.organisation.province, name="A Different Organisation",
        entity_type="Cooperative", district="Harare",
        actor_family=main_case.organisation.actor_family, value_chain="Horticulture",
        size_class=main_case.organisation.size_class,
    )
    other_case = create_sample_case(organisation=other_org, stratum=main_case.stratum, sample_type="MAIN", year=2026)
    raw_token, _, _ = issue_invitation(other_case)

    client = APIClient()
    resp = client.post(
        "/api/v1/proit/respondent-verify/",
        {"token": raw_token, "field_id": field.id, "status": "YES_CORRECT"},
        format="json",
    )
    assert resp.status_code == 404
