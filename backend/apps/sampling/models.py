"""
Sampling models: Organisation, StratumDefinition, SampleCase.

Main-400/Reserve-400 integrity is a database-level control, not a
spreadsheet convention -- see docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md and
AGENTS.md ground rule 4. Every invitation-issuing code path must call
sampling.services.is_invitable() rather than checking SampleCase.status
inline elsewhere, so the lock is enforced in exactly one place
(docs/08_BACKEND_ARCHITECTURE.md).

CATEGORY LISTS (updated 2026-09-12): actor_family/size_class now use the
real, PI-approved category sets from the actual approved sampling register
(ABI_ABF-FST_QUAN_Latest_Register's "Stratum Allocation" sheet), which also
confirmed the real stratification design is Province x Actor Family x Size
Class only -- Value Chain plays no part in it. value_chain and entity_type
are deliberately free text, not a small choice set, since the real
register's data for those two fields is far richer than any fixed dropdown
(hundreds of distinct, sometimes multi-valued entries) -- see
StratumDefinition and Organisation's own docstrings. Province codes/names
are objective public fact (Zimbabwe's 10 provinces).
"""

from django.core.exceptions import ValidationError
from django.db import models


class Province(models.TextChoices):
    HARARE = "HARARE", "Harare"
    BULAWAYO = "BULAWAYO", "Bulawayo"
    MANICALAND = "MANICALAND", "Manicaland"
    MASHONALAND_CENTRAL = "MASHONALAND_CENTRAL", "Mashonaland Central"
    MASHONALAND_EAST = "MASHONALAND_EAST", "Mashonaland East"
    MASHONALAND_WEST = "MASHONALAND_WEST", "Mashonaland West"
    MASVINGO = "MASVINGO", "Masvingo"
    MATABELELAND_NORTH = "MATABELELAND_NORTH", "Matabeleland North"
    MATABELELAND_SOUTH = "MATABELELAND_SOUTH", "Matabeleland South"
    MIDLANDS = "MIDLANDS", "Midlands"


# Two-letter code per province for Master_ID generation
# (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md: "MID-<province-code(2)>-<seq>").
PROVINCE_CODE = {
    Province.HARARE: "HA",
    Province.BULAWAYO: "BU",
    Province.MANICALAND: "MA",
    Province.MASHONALAND_CENTRAL: "MC",
    Province.MASHONALAND_EAST: "ME",
    Province.MASHONALAND_WEST: "MW",
    Province.MASVINGO: "MV",
    Province.MATABELELAND_NORTH: "MN",
    Province.MATABELELAND_SOUTH: "MS",
    Province.MIDLANDS: "MI",
}


class ActorFamily(models.TextChoices):
    """The real, PI-approved category set (2026-09-12), replacing an earlier
    engineering placeholder -- see the approved sampling register's own
    "Stratum Allocation" sheet (ABI_ABF-FST_QUAN_Latest_Register), which
    uses exactly these eight values as the actual Actor Family stratification
    variable."""

    AGGREGATION_MARKET_RETAIL = "AGGREGATION_MARKET_RETAIL", "Aggregation / Market / Retail"
    INPUTS_MECHANISATION = "INPUTS_MECHANISATION", "Inputs / Mechanisation"
    PROCESSING_MANUFACTURING = "PROCESSING_MANUFACTURING", "Processing / Manufacturing"
    PRODUCER_PRIMARY = "PRODUCER_PRIMARY", "Producer / Primary"
    SERVICES_ENABLING = "SERVICES_ENABLING", "Services / Enabling"
    FINANCE_INSURANCE = "FINANCE_INSURANCE", "Finance / Insurance"
    INSTITUTIONAL_COMMERCIAL_UNIT = "INSTITUTIONAL_COMMERCIAL_UNIT", "Institutional Commercial Unit"
    OTHER_VERIFY = "OTHER_VERIFY", "Other / Verify"


class SizeClass(models.TextChoices):
    """The real, PI-approved category set (2026-09-12), replacing an earlier
    engineering placeholder -- matches the approved sampling register's own
    "Stratum Allocation" sheet exactly."""

    MICRO = "MICRO", "Micro"
    SME = "SME", "SME"
    UNKNOWN = "UNKNOWN", "Unknown"
    LARGE_CORPORATE = "LARGE_CORPORATE", "Large / Corporate"
    INSTITUTIONAL_OTHER = "INSTITUTIONAL_OTHER", "Institutional / Other"


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"
    UNREACHABLE = "UNREACHABLE", "Unreachable"
    DUPLICATE = "DUPLICATE", "Duplicate"


class IdentifierSequence(models.Model):
    """Backing store for the DB-generated monotonic sequences behind
    Master_ID/Sample_ID generation (sampling.services) -- one row per
    province code ("MASTER_ID:HA") or study year ("SAMPLE_ID:2026").
    Incremented under `select_for_update()` so concurrent imports can never
    produce a duplicate identifier."""

    key = models.CharField(max_length=32, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.key}={self.last_value}"


class StratumDefinition(models.Model):
    """Stratified by Province x Actor Family x Size Class only (2026-09-12) --
    the approved sampling register's own "Stratum Allocation" sheet defines
    the study's strata this way; Value Chain plays no part in the actual
    stratification design, despite an earlier engineering assumption that it
    did. See Organisation.value_chain for where that information now lives
    (a free-text descriptive field, not a stratification key)."""

    # Widened 2026-09-12: the real category values are long enough that
    # "<province>-<actor_family>-<size_class>" can exceed 64 chars (e.g.
    # "MASHONALAND_CENTRAL-INSTITUTIONAL_COMMERCIAL_UNIT-INSTITUTIONAL_OTHER").
    code = models.CharField(max_length=96, unique=True)
    province = models.CharField(max_length=32, choices=Province.choices)
    actor_family = models.CharField(max_length=32, choices=ActorFamily.choices)
    size_class = models.CharField(max_length=32, choices=SizeClass.choices)
    target_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["province", "actor_family", "size_class"],
                name="unique_stratum_definition_combo",
            ),
        ]

    def __str__(self):
        return self.code


class Organisation(models.Model):
    """Master_ID is generated exclusively at import time
    (sampling.services.generate_master_id) -- never user-entered, immutable
    for the life of the record (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).

    entity_type/value_chain are free text (2026-09-12), not a small choice
    set -- the approved sampling register's real data for these two fields
    is far richer than a fixed dropdown can hold (hundreds of distinct,
    sometimes semicolon-joined multi-values), unlike actor_family/size_class
    above, which the register's own stratification design treats as a clean,
    small, controlled vocabulary.
    """

    master_id = models.CharField(max_length=16, unique=True, editable=False)
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=255, blank=True)
    province = models.CharField(max_length=32, choices=Province.choices)
    district = models.CharField(max_length=255)
    actor_family = models.CharField(max_length=32, choices=ActorFamily.choices)
    value_chain = models.CharField(max_length=255, blank=True)
    size_class = models.CharField(max_length=32, choices=SizeClass.choices)
    # Losslessly preserves register-provenance fields with no dedicated model
    # field (e.g. the source ABI Master_ID this organisation's row carried in
    # the approved register) -- nothing invented, nothing discarded.
    metadata = models.JSONField(default=dict, blank=True)
    verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    verified_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="verified_organisations",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.master_id} — {self.name}"


class SampleType(models.TextChoices):
    MAIN = "MAIN", "Main"
    RESERVE = "RESERVE", "Reserve"


class ReserveStatus(models.TextChoices):
    """SampleCase.status values for sample_type=RESERVE only."""

    LOCKED = "LOCKED", "Locked"
    ACTIVATED = "ACTIVATED", "Activated"


class WorkflowStatus(models.TextChoices):
    """S00-S16, docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md. SampleCase.status
    for sample_type=MAIN mirrors this engine directly."""

    S00_SELECTED_MAIN = "S00", "Selected Main"
    S01_VERIFICATION_REQUIRED = "S01", "Verification required"
    S02_ORGANISATION_VERIFIED = "S02", "Organisation verified"
    S03_ELIGIBLE_RESPONDENT_IDENTIFIED = "S03", "Eligible respondent identified"
    S04_INVITATION_PREPARED = "S04", "Invitation prepared"
    S05_INVITATION_SENT = "S05", "Invitation sent"
    S06_INVITATION_OPENED = "S06", "Invitation opened"
    S07_SURVEY_STARTED = "S07", "Survey started"
    S08_SURVEY_SUBMITTED = "S08", "Survey submitted"
    S09_QA_QUERY = "S09", "QA query"
    S10_QA_PASSED = "S10", "QA passed"
    S11_COMPLETED = "S11", "Completed"
    S12_REFUSED = "S12", "Refused"
    S13_NONRESPONSE = "S13", "Nonresponse"
    S14_INELIGIBLE = "S14", "Ineligible"
    S15_DUPLICATE_INACTIVE = "S15", "Duplicate/inactive"
    S16_RESERVE_ELIGIBLE = "S16", "Reserve eligible for activation"


class ActivationReason(models.TextChoices):
    INELIGIBLE = "INELIGIBLE", "Ineligible"
    INACTIVE = "INACTIVE", "Inactive"
    DUPLICATE = "DUPLICATE", "Duplicate"
    REFUSAL = "REFUSAL", "Refusal"
    NONRESPONSE_EXHAUSTED = "NONRESPONSE_EXHAUSTED", "Nonresponse exhausted"


class SampleCase(models.Model):
    sample_id = models.CharField(max_length=16, unique=True, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="sample_cases"
    )
    stratum = models.ForeignKey(
        StratumDefinition, on_delete=models.PROTECT, related_name="sample_cases"
    )
    sample_type = models.CharField(max_length=8, choices=SampleType.choices)
    matched_case = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="matched_by",
    )
    # For MAIN: mirrors WorkflowStatus (S00-S16). For RESERVE: ReserveStatus
    # (LOCKED/ACTIVATED). Kept as one field per docs/05_DATABASE_ARCHITECTURE.md;
    # the two choice sets never overlap in value, so no ambiguity in practice.
    status = models.CharField(max_length=16)
    workflow_status = models.CharField(
        max_length=8, choices=WorkflowStatus.choices, null=True, blank=True
    )
    activation_reason = models.CharField(
        max_length=32, choices=ActivationReason.choices, null=True, blank=True
    )
    activated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="activated_reserves",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    activation_evidence_note = models.TextField(blank=True)
    # Which Contact RA this case is assigned to -- docs/18's access matrix
    # grants Contact RA "assigned cases" only, not every case. Nullable:
    # an unassigned case is simply invisible to every Contact RA until a
    # Field Coordinator/Admin assigns one (api.permissions.CanViewSampleCases
    # and CanManageContact enforce this via each view's get_queryset(), not
    # here -- this field only records the assignment).
    assigned_ra = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_sample_cases",
    )
    # Losslessly preserves register-provenance fields with no dedicated model
    # field (source Sample_ID, Priority, QUAN Eligibility, Desk Verification
    # Gate, Verification Evidence, Selection Method, Deployment Status, etc.
    # from the approved sampling register) -- nothing invented, nothing
    # discarded.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # docs/05_DATABASE_ARCHITECTURE.md "Integrity rules": activation_reason,
        # activated_by and activated_at must all be set together.
        activation_fields = (self.activation_reason, self.activated_by_id, self.activated_at)
        if any(activation_fields) and not all(activation_fields):
            raise ValidationError(
                "activation_reason, activated_by and activated_at must all be "
                "set together, or none of them."
            )
        if self.sample_type == SampleType.RESERVE and self.workflow_status:
            raise ValidationError("RESERVE cases use `status` (LOCKED/ACTIVATED), not workflow_status.")
        if self.sample_type == SampleType.MAIN and not self.workflow_status:
            raise ValidationError("MAIN cases must have a workflow_status.")

    def __str__(self):
        return self.sample_id
