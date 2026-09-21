"""
PROIT (Pre-Interview Respondent & Organisation Intelligence and
Verification Tool) -- a pre-interview desk-research layer, specified in
ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx. Before a respondent is
contacted, researchers gather publicly available background facts about
the organisation/respondent from documentary sources, record provenance
for each, and a human reviews and locks a "pre-profile". The respondent
then confirms/corrects/declines each pre-filled fact instead of answering
from zero -- that substitution is the actual burden-reduction mechanism,
not any change to the study's own measurement instruments.

Three-value architecture (document Section 7) is the central design
constraint: the preliminary documentary value, the respondent's own
answer, and a researcher-reconciled value are three separate fields on
PreProfileField, never merged or overwritten into each other. This
prevents documentary evidence from silently becoming respondent evidence.

PROIT_FIELD_CATALOG is the field-ID whitelist transcribed from the
document's own Section 6 modules A-G (the pre-fillable descriptive
fields). It exists specifically so a PreProfileField can never reference
one of the frozen ABI/NFM/Digital-Readiness/Institutional-Environment/FST
scale items -- the document's own "non-negotiable deployment rule" is
enforced here as a closed set, not by convention.
"""

from django.core.exceptions import ValidationError
from django.db import models


class Module(models.TextChoices):
    CASE_CONTROL = "CASE_CONTROL", "A. Case Control & Routing"
    RESPONDENT_PROFILE = "RESPONDENT_PROFILE", "B. Respondent Professional Profile"
    ORGANISATION_PROFILE = "ORGANISATION_PROFILE", "C. Organisation Profile"
    OPERATIONS_MARKETS = "OPERATIONS_MARKETS", "D. Operations & Markets"
    FINANCE_CONTEXT = "FINANCE_CONTEXT", "E. Public Finance/Bankability Context"
    INSTITUTIONAL_DIGITAL = "INSTITUTIONAL_DIGITAL", "F. Institutional & Digital Context"


class FieldRoute(models.TextChoices):
    QUAN = "QUAN", "QUAN only"
    KII = "KII", "KII only"
    BOTH = "BOTH", "Both QUAN and KII"


# field_id -> (label, module, route). Transcribed verbatim from the
# document's Section 6 tables, modules A-F only (G is provenance metadata,
# modelled as EvidenceSource below; H/I/J are outcome/workflow fields,
# modelled as PreProfile fields directly, not per-field values).
PROIT_FIELD_CATALOG = {
    # A. Case Control & Routing (not pre-filled -- routing/identity only,
    # but listed so the catalog matches the document exactly).
    "organisation_selected": ("Selected organisation name", Module.CASE_CONTROL, FieldRoute.BOTH),
    "respondent_selected": ("Selected respondent/professional role", Module.CASE_CONTROL, FieldRoute.BOTH),
    # B. Respondent Professional Profile
    "respondent_name": ("Respondent name", Module.RESPONDENT_PROFILE, FieldRoute.BOTH),
    "job_title": ("Current designation", Module.RESPONDENT_PROFILE, FieldRoute.BOTH),
    "role_category": ("Role category", Module.RESPONDENT_PROFILE, FieldRoute.BOTH),
    "decision_authority": ("Decision-making relevance to study", Module.RESPONDENT_PROFILE, FieldRoute.BOTH),
    "public_professional_experience": ("Relevant public professional experience summary", Module.RESPONDENT_PROFILE, FieldRoute.BOTH),
    # C. Organisation Profile
    "legal_name": ("Registered/legal organisation name", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "trading_name": ("Trading/brand name", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "organisation_type": ("Organisation type", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "year_established": ("Year established", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "hq_province": ("HQ province", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "hq_district": ("HQ district", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "geographic_coverage": ("Operating geography", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    "firm_size_public": ("Publicly indicated size band", Module.ORGANISATION_PROFILE, FieldRoute.BOTH),
    # D. Operations & Markets
    "primary_value_chain": ("Primary value chain", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    "value_chain_role": ("Value-chain role(s)", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    "key_products": ("Key products/services", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    "market_reach": ("Market reach", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    "known_offtake_contracts": ("Publicly documented offtake/contract arrangements", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    "aggregation_model": ("Publicly documented aggregation/outgrower model", Module.OPERATIONS_MARKETS, FieldRoute.BOTH),
    # E. Public Finance/Bankability Context
    "public_finance_facilities": ("Publicly disclosed lenders/finance facilities", Module.FINANCE_CONTEXT, FieldRoute.BOTH),
    "public_collateral_tenure": ("Publicly documented tenure/collateral status", Module.FINANCE_CONTEXT, FieldRoute.BOTH),
    "public_insurance": ("Publicly disclosed insurance/risk-transfer arrangements", Module.FINANCE_CONTEXT, FieldRoute.BOTH),
    "audited_reports_available": ("Audited financial statements publicly available", Module.FINANCE_CONTEXT, FieldRoute.BOTH),
    "public_financial_metrics": ("Public financial metrics relevant to context", Module.FINANCE_CONTEXT, FieldRoute.BOTH),
    # F. Institutional & Digital Context
    "licences_certifications": ("Known licences/certifications/standards", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
    "digital_platforms": ("Known digital platforms/systems", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
    "traceability_public": ("Public evidence of traceability/record systems", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
    "government_programmes": ("Participation in public/development programmes", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
    "institutional_memberships": ("Relevant industry/association memberships", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
    "infrastructure_assets_public": ("Publicly documented productive/infrastructure assets", Module.INSTITUTIONAL_DIGITAL, FieldRoute.BOTH),
}


class Confidence(models.TextChoices):
    """Section 4's evidence confidence/display rules. LOW is never shown to
    a respondent as a fact -- see proit.services.field_is_displayable()."""

    HIGH = "HIGH", "High -- authoritative or two concordant sources"
    MODERATE = "MODERATE", "Moderate -- one credible source, or minor staleness"
    LOW = "LOW", "Low -- weak/old/ambiguous/uncorroborated"


class GapClassification(models.TextChoices):
    """Workflow step 8 (document Section 2 / Section 9)."""

    VERIFY_ONLY = "VERIFY_ONLY", "Verify only"
    VERIFY_AND_PROBE = "VERIFY_AND_PROBE", "Verify and probe"
    ASK_FULL = "ASK_FULL", "Ask full"
    SKIP_BACKGROUND_ONLY = "SKIP_BACKGROUND_ONLY", "Skip (background only)"


class VerificationStatusCode(models.TextChoices):
    """Appendix A."""

    YES_CORRECT = "YES_CORRECT", "Respondent confirms preliminary value"
    NO_CORRECT_VALUE_PROVIDED = "NO_CORRECT_VALUE_PROVIDED", "Respondent rejects and supplies corrected value"
    PARTLY_CORRECT = "PARTLY_CORRECT", "Respondent qualifies or updates the value"
    DO_NOT_KNOW = "DO_NOT_KNOW", "Respondent cannot verify"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY", "Respondent declines"
    NOT_APPLICABLE = "NOT_APPLICABLE", "Field does not apply"


class SourceAuthority(models.TextChoices):
    """Section 5's four-tier source priority hierarchy."""

    TIER_1_STATUTORY = "TIER_1_STATUTORY", "Tier 1 -- statutory/official register or audited report"
    TIER_2_INSTITUTIONAL = "TIER_2_INSTITUTIONAL", "Tier 2 -- official website, investor report, association record"
    TIER_3_MEDIA = "TIER_3_MEDIA", "Tier 3 -- reputable media, conference bio, professional profile"
    TIER_4_SOCIAL = "TIER_4_SOCIAL", "Tier 4 -- corroborated public social/platform content"


class ReconciliationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    RECONCILED = "RECONCILED", "Reconciled"
    UNRESOLVED = "UNRESOLVED", "Unresolved"


class PreProfile(models.Model):
    """One per SampleCase (QUAN) or KIIRecord (KII) -- exactly one of the
    two, same pattern as consent.ConsentRecord / contacts.Appointment."""

    sample_case = models.ForeignKey(
        "sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE,
        related_name="pre_profiles",
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE,
        related_name="pre_profiles",
    )

    # Module H (case-level parts; verification_comment is per-field, see
    # PreProfileField).
    verification_intro_ack = models.BooleanField(default=False)
    permission_to_use_correction = models.BooleanField(null=True, blank=True)
    verification_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    background_questions_avoided = models.PositiveIntegerField(default=0)
    burden_reduction_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Module I -- Adaptive KII Gap Engine (KII route only; blank for QUAN).
    known_evidence_summary = models.TextField(blank=True)
    unresolved_gaps = models.TextField(blank=True)
    contradictions = models.TextField(blank=True)
    priority_probe_questions = models.TextField(blank=True)
    role_specific_module = models.CharField(max_length=64, blank=True)
    executive_short_form = models.BooleanField(default=False)

    # Module J -- QA, Lock & Reconciliation
    researcher_reviewed = models.BooleanField(default=False)
    qa_reviewer = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="proit_qa_reviews",
    )
    prepopulation_locked_at = models.DateTimeField(null=True, blank=True)
    interview_completed_at = models.DateTimeField(null=True, blank=True)
    reconciliation_status = models.CharField(
        max_length=16, choices=ReconciliationStatus.choices, default=ReconciliationStatus.PENDING,
    )
    protocol_deviation = models.BooleanField(default=False)
    deviation_note = models.TextField(blank=True)
    # Set when the finished profile has been sent to KoboToolbox (kobo_submit.py).
    kobo_submission_uuid = models.CharField(max_length=64, blank=True)
    kobo_submitted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if bool(self.sample_case_id) == bool(self.kii_record_id):
            raise ValidationError("Exactly one of sample_case/kii_record must be set.")

    def __str__(self):
        target = self.sample_case_id and f"case {self.sample_case_id}" or f"kii {self.kii_record_id}"
        return f"PreProfile({target})"


class PreProfileField(models.Model):
    """One row per field_id per pre-profile -- the three-value architecture
    (document Section 7) lives here: preliminary_documentary_value,
    respondent_value and reconciled_value are independent and never
    overwrite one another."""

    pre_profile = models.ForeignKey(PreProfile, on_delete=models.CASCADE, related_name="fields")
    field_id = models.CharField(max_length=64)
    module = models.CharField(max_length=32, choices=Module.choices)
    label = models.CharField(max_length=255)
    route = models.CharField(max_length=8, choices=FieldRoute.choices, default=FieldRoute.BOTH)

    preliminary_documentary_value = models.TextField(blank=True)
    respondent_value = models.TextField(blank=True)
    reconciled_value = models.TextField(blank=True)

    confidence = models.CharField(max_length=16, choices=Confidence.choices, blank=True)
    gap_classification = models.CharField(max_length=24, choices=GapClassification.choices, blank=True)
    verification_status = models.CharField(max_length=32, choices=VerificationStatusCode.choices, blank=True)
    verification_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Creation order. Without it Postgres returns rows in physical order,
        # which changes once a row is updated (locking a profile rewrites
        # every field) -- the respondent's facts could swap places between
        # page loads. Found by the E2E suite 2026-09-14.
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["pre_profile", "field_id"], name="unique_pre_profile_field"),
        ]

    def clean(self):
        if self.field_id not in PROIT_FIELD_CATALOG:
            raise ValidationError(
                f"{self.field_id!r} is not in PROIT_FIELD_CATALOG -- PROIT may only pre-fill the "
                "non-core descriptive fields documented in modules A-F, never a frozen study "
                "construct item."
            )

    def __str__(self):
        return f"{self.field_id} ({self.pre_profile_id})"


class EvidenceSource(models.Model):
    """Module G -- documentary provenance. One-to-many with
    PreProfileField: a field can cite multiple sources, and sources can
    conflict (source_conflict) -- neither is resolved automatically."""

    source_record_id = models.CharField(max_length=32, unique=True, editable=False)
    field = models.ForeignKey(PreProfileField, on_delete=models.CASCADE, related_name="sources")
    source_title = models.CharField(max_length=512)
    source_type = models.CharField(max_length=32, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    source_date = models.DateField(null=True, blank=True)
    access_date = models.DateField(null=True, blank=True)
    locator = models.CharField(max_length=1024, blank=True)
    source_authority = models.CharField(max_length=24, choices=SourceAuthority.choices, blank=True)
    source_confidence = models.CharField(max_length=16, choices=Confidence.choices)
    source_conflict = models.BooleanField(default=False)
    researcher_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="proit_evidence_added",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_record_id} -- {self.source_title}"


class AIResearchStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    DONE = "DONE", "Done"
    FAILED = "FAILED", "Failed"


class AIResearchRun(models.Model):
    """One AI desk-research pass over an organisation (and the respondent's
    published professional role) for a pre-profile. The AI only ever PROPOSES:
    nothing here reaches a PreProfileField until a researcher accepts it
    (AIProposal). Recorded so the study can say exactly what was AI-assisted,
    with which model, and what it searched."""

    pre_profile = models.ForeignKey(PreProfile, on_delete=models.CASCADE, related_name="ai_runs")
    status = models.CharField(max_length=8, choices=AIResearchStatus.choices, default=AIResearchStatus.RUNNING)
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    model = models.CharField(max_length=64, blank=True)
    searches_used = models.PositiveIntegerField(default=0)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    summary = models.TextField(blank=True)  # the AI's own note on what it looked for and its limits
    error = models.TextField(blank=True)
    dropped = models.JSONField(default=list, blank=True)  # findings the server refused, and why

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"AIResearchRun({self.pre_profile_id} {self.status})"


class AIProposalStatus(models.TextChoices):
    PROPOSED = "PROPOSED", "Proposed"
    NOT_FOUND = "NOT_FOUND", "Not found publicly"
    ACCEPTED = "ACCEPTED", "Accepted"
    EDITED = "EDITED", "Accepted with edits"
    REJECTED = "REJECTED", "Rejected"


class AIProposal(models.Model):
    run = models.ForeignKey(AIResearchRun, on_delete=models.CASCADE, related_name="proposals")
    pre_profile = models.ForeignKey(PreProfile, on_delete=models.CASCADE, related_name="ai_proposals")
    field_id = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=AIProposalStatus.choices, default=AIProposalStatus.PROPOSED)
    proposed_value = models.TextField(blank=True)
    final_value = models.TextField(blank=True)
    confidence = models.CharField(max_length=16, choices=Confidence.choices, blank=True)
    sources = models.JSONField(default=list, blank=True)  # [{title, url, publisher, published, quote, authority}]
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    profile_field = models.ForeignKey(
        PreProfileField, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_proposals"
    )  # set when accepted

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["run", "field_id"], name="unique_ai_proposal_per_run_field")]

    def __str__(self):
        return f"AIProposal({self.field_id} {self.status})"
