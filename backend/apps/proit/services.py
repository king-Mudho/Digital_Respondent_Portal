"""
PROIT business rules, transcribed directly from the document's own
"Non-negotiable deployment rules" (Section 1) and workflow (Section 2):

- No value enters the respondent record without a source ID and
  provenance trail -> enforced in lock_pre_profile().
- A human researcher must review before the pre-profile is locked ->
  enforced in lock_pre_profile().
- Respondent corrections are stored separately; they never erase the
  documentary value -> structural (separate model fields), plus
  record_verification() only runs after lock, never touching
  preliminary_documentary_value.
- Low-confidence or conflicting evidence is not presented as fact; it is
  routed to ASK FULL or VERIFY AND PROBE -> compute_field_confidence() /
  compute_gap_classification().
- Once locked, documentary values and their evidence are immutable -> add_
  evidence()/set_documentary_value() both raise PreProfileLocked afterward.
"""

from django.db import transaction
from django.utils import timezone

from apps.sampling.services import next_sequence

from .models import (
    Confidence,
    EvidenceSource,
    GapClassification,
    PreProfile,
    PreProfileField,
    VerificationStatusCode,
)


class PreProfileError(Exception):
    pass


class PreProfileLocked(PreProfileError):
    pass


class PreProfileNotLocked(PreProfileError):
    pass


def generate_source_record_id() -> str:
    """EVID-<sequence(5)>, e.g. EVID-00042. Same DB-sequence approach as
    Master_ID/Sample_ID/KII_ID/DOC_ID."""
    seq = next_sequence("PROIT_EVIDENCE_ID")
    return f"EVID-{seq:05d}"


def create_pre_profile(*, sample_case=None, kii_record=None) -> PreProfile:
    profile = PreProfile(sample_case=sample_case, kii_record=kii_record)
    profile.full_clean()
    profile.save()
    return profile


def add_field(pre_profile: PreProfile, field_id: str, *, documentary_value: str = "") -> PreProfileField:
    """Adds one of the catalog's fields to a pre-profile. Raises via
    PreProfileField.clean()/full_clean() if field_id isn't in
    PROIT_FIELD_CATALOG -- see models.py module docstring."""
    if pre_profile.prepopulation_locked_at is not None:
        raise PreProfileLocked("Cannot add a field to an already-locked pre-profile.")

    from .models import PROIT_FIELD_CATALOG

    label, module, route = PROIT_FIELD_CATALOG[field_id]
    field = PreProfileField(
        pre_profile=pre_profile, field_id=field_id, module=module, label=label, route=route,
        preliminary_documentary_value=documentary_value,
    )
    field.full_clean()
    field.save()
    return field


def compute_field_confidence(field: PreProfileField) -> str:
    """Section 4's confidence rules, derived from this field's own
    evidence: an authoritative (Tier 1) source rated HIGH, or two
    non-conflicting credible sources, is HIGH; one credible source is
    MODERATE; anything else (no evidence, or only weak/conflicting
    evidence) is LOW."""
    sources = list(field.sources.all())
    if not sources:
        return Confidence.LOW

    has_conflict = any(s.source_conflict for s in sources)
    credible = [s for s in sources if s.source_confidence in (Confidence.HIGH, Confidence.MODERATE)]

    if any(s.source_authority == "TIER_1_STATUTORY" and s.source_confidence == Confidence.HIGH for s in sources):
        return Confidence.HIGH
    if len(credible) >= 2 and not has_conflict:
        return Confidence.HIGH
    if len(credible) >= 1:
        return Confidence.MODERATE
    return Confidence.LOW


@transaction.atomic
def add_evidence(
    field: PreProfileField, *, source_title: str, source_confidence: str, created_by=None, **fields
) -> EvidenceSource:
    if field.pre_profile.prepopulation_locked_at is not None:
        raise PreProfileLocked("Cannot add evidence to an already-locked pre-profile.")

    source = EvidenceSource(
        source_record_id=generate_source_record_id(),
        field=field,
        source_title=source_title,
        source_confidence=source_confidence,
        created_by=created_by,
        **fields,
    )
    source.full_clean()
    source.save()

    field.confidence = compute_field_confidence(field)
    field.save(update_fields=["confidence"])
    return source


def compute_gap_classification(field: PreProfileField) -> str:
    """Workflow step 8 / Section 9's KII routing table, applied uniformly
    to QUAN and KII. A researcher can still manually override to
    SKIP_BACKGROUND_ONLY afterward for a field judged not worth probing."""
    if not field.preliminary_documentary_value:
        return GapClassification.ASK_FULL
    if field.confidence == Confidence.LOW:
        return GapClassification.ASK_FULL
    if field.sources.filter(source_conflict=True).exists():
        return GapClassification.VERIFY_AND_PROBE
    return GapClassification.VERIFY_ONLY


@transaction.atomic
def lock_pre_profile(pre_profile: PreProfile, *, reviewer) -> PreProfile:
    """The pre-population lock (workflow step 5). Requires every
    documentary value to carry at least one evidence source (the
    document's "no value without a source ID and provenance trail" rule),
    and always records who reviewed it -- never lockable anonymously."""
    if pre_profile.prepopulation_locked_at is not None:
        raise PreProfileLocked("This pre-profile is already locked.")

    fields = list(pre_profile.fields.all())
    for field in fields:
        if field.preliminary_documentary_value and not field.sources.exists():
            raise PreProfileError(
                f"Field {field.field_id!r} has a documentary value but no evidence source -- "
                "every pre-filled value must carry a provenance trail before locking."
            )

    for field in fields:
        field.gap_classification = compute_gap_classification(field)
        field.save(update_fields=["gap_classification"])

    pre_profile.researcher_reviewed = True
    pre_profile.qa_reviewer = reviewer
    pre_profile.prepopulation_locked_at = timezone.now()
    pre_profile.save(update_fields=["researcher_reviewed", "qa_reviewer", "prepopulation_locked_at"])
    return pre_profile


def field_is_displayable(field: PreProfileField) -> bool:
    """Section 4: a LOW-confidence value is never shown to the respondent
    as a proposed fact -- it becomes a full question instead (handled by
    the respondent-facing serializer omitting the value, not just hiding
    it client-side)."""
    return bool(field.preliminary_documentary_value) and field.confidence != Confidence.LOW


def record_verification(
    field: PreProfileField, *, status: str, respondent_value: str = "", comment: str = ""
) -> PreProfileField:
    """Verification (workflow step 7) only ever happens after lock -- the
    document's own step ordering (5. lock -> 6. consent -> 7.
    verification). respondent_value/verification_comment are new fields on
    the row; preliminary_documentary_value is never touched here, so a
    correction can never erase the documentary record."""
    if field.pre_profile.prepopulation_locked_at is None:
        raise PreProfileNotLocked("Cannot record a respondent verification before the pre-profile is locked.")
    if status not in VerificationStatusCode.values:
        raise PreProfileError(f"Invalid verification status: {status!r}")

    field.verification_status = status
    field.respondent_value = respondent_value
    field.verification_comment = comment
    field.save(update_fields=["verification_status", "respondent_value", "verification_comment"])
    return field


def reconcile_field(field: PreProfileField, *, reconciled_value: str) -> PreProfileField:
    """Researcher-coded reconciled value (Section 7), applied after the
    respondent has verified -- never overwrites documentary or respondent
    values, just records the analyst's final coded position."""
    field.reconciled_value = reconciled_value
    field.save(update_fields=["reconciled_value"])
    return field


def compute_burden_metrics(pre_profile: PreProfile) -> PreProfile:
    """Section 11's Interview Burden Reduction Score: 100 x background
    questions avoided / eligible background questions."""
    fields = list(pre_profile.fields.all())
    eligible = len(fields)
    avoided = sum(1 for f in fields if f.gap_classification in (
        GapClassification.VERIFY_ONLY, GapClassification.VERIFY_AND_PROBE, GapClassification.SKIP_BACKGROUND_ONLY,
    ))
    pre_profile.background_questions_avoided = avoided
    pre_profile.burden_reduction_score = round(100 * avoided / eligible, 2) if eligible else None
    pre_profile.save(update_fields=["background_questions_avoided", "burden_reduction_score"])
    return pre_profile


# Section 10's probe-template library, role -> (trigger description,
# template). Every template's original bracketed placeholder (e.g.
# "{product/facility}", "{offtake}") is normalised to a single {evidence}
# slot so render_probe_template() can substitute uniformly; a template
# with no placeholder in the original document simply ignores the value
# passed in.
PROBE_TEMPLATES = {
    "FINANCE_LENDER": (
        "Public product evidence exists",
        "We identified {evidence}. What are the actual approval criteria, rejection drivers, "
        "pricing/risk-sharing and performance experience?",
    ),
    "FARMER_AGRIBUSINESS": (
        "Offtake/contract found",
        "The organisation appears to have {evidence}. How reliable is it in generating "
        "predictable cash flow and lender confidence?",
    ),
    "GOVERNMENT_POLICY": (
        "Policy commitment found",
        "The policy commits to {evidence}. What has been implemented, what evidence exists, "
        "and what still blocks bankability?",
    ),
    "RDC_PROVINCE": (
        "Plan/project found",
        "The plan identifies {evidence}. Has it changed market access, transaction costs or "
        "access to finance?",
    ),
    "PROCESSOR_AGGREGATOR": (
        "Outgrower/aggregation found",
        "How are farmers selected, verified, financed, paid and monitored, and who bears "
        "production/market risk?",
    ),
    "INSURANCE_GUARANTEE": (
        "Risk instrument found",
        "What losses/risks are actually covered, how does the product affect lender decisions, "
        "and what limits uptake?",
    ),
    "RESEARCH_ACADEMIC": (
        "Published finding found",
        "Your published work reports {evidence}. Does this still hold in 2026, and what "
        "evidence would challenge it?",
    ),
}


def render_probe_template(role: str, evidence: str = "") -> str:
    if role not in PROBE_TEMPLATES:
        raise PreProfileError(f"Unknown probe template role: {role!r}")
    _, template = PROBE_TEMPLATES[role]
    try:
        return template.format(evidence=evidence)
    except (KeyError, IndexError):
        return template
