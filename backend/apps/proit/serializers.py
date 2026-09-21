from rest_framework import serializers

from .models import AIProposal, AIResearchRun, EvidenceSource, PreProfile, PreProfileField


class EvidenceSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceSource
        fields = [
            "id", "source_record_id", "field", "source_title", "source_type", "publisher",
            "source_date", "access_date", "locator", "source_authority", "source_confidence",
            "source_conflict", "researcher_notes", "created_by", "created_at",
        ]
        read_only_fields = ["id", "source_record_id", "created_by", "created_at"]


class PreProfileFieldSerializer(serializers.ModelSerializer):
    sources = EvidenceSourceSerializer(many=True, read_only=True)

    class Meta:
        model = PreProfileField
        fields = [
            "id", "pre_profile", "field_id", "module", "label", "route",
            "preliminary_documentary_value", "respondent_value", "reconciled_value",
            "confidence", "gap_classification", "verification_status", "verification_comment",
            "sources", "created_at", "updated_at",
        ]
        # respondent_value/verification_status/verification_comment are set only via
        # proit.services.record_verification() (enforces the lock-before-verify rule);
        # reconciled_value only via reconcile_field(); confidence/gap_classification
        # are computed, never client-supplied.
        read_only_fields = [
            "id", "confidence", "gap_classification", "respondent_value",
            "verification_status", "verification_comment", "reconciled_value",
            "created_at", "updated_at",
        ]


class PreProfileSerializer(serializers.ModelSerializer):
    fields = PreProfileFieldSerializer(many=True, read_only=True)
    sample_id = serializers.CharField(source="sample_case.sample_id", read_only=True, default=None)
    kii_id = serializers.CharField(source="kii_record.kii_id", read_only=True, default=None)

    class Meta:
        model = PreProfile
        fields = [
            "id", "sample_case", "kii_record", "sample_id", "kii_id",
            "verification_intro_ack", "permission_to_use_correction", "verification_duration_seconds",
            "background_questions_avoided", "burden_reduction_score",
            "known_evidence_summary", "unresolved_gaps", "contradictions",
            "priority_probe_questions", "role_specific_module", "executive_short_form",
            "researcher_reviewed", "qa_reviewer", "prepopulation_locked_at",
            "interview_completed_at", "reconciliation_status", "protocol_deviation",
            "deviation_note", "fields", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "researcher_reviewed", "qa_reviewer", "prepopulation_locked_at",
            "background_questions_avoided", "burden_reduction_score",
            # Set only by the interview and reconciliation actions (they enforce the rules a plain PATCH could skip).
            "interview_completed_at", "reconciliation_status", "protocol_deviation", "deviation_note",
            "created_at", "updated_at",
        ]


class RespondentPreProfileFieldSerializer(serializers.ModelSerializer):
    """Respondent-facing only -- never exposes source-internal notes, per
    the document's own Developer Implementation Contract ("never expose
    source-internal notes to respondents"). LOW-confidence fields are
    filtered out entirely before this serializer ever runs (see
    proit.views), not just hidden client-side."""

    class Meta:
        model = PreProfileField
        fields = ["id", "field_id", "label", "preliminary_documentary_value", "confidence"]


class AIProposalSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = AIProposal
        fields = [
            "id", "field_id", "label", "status", "proposed_value", "final_value", "confidence", "sources",
            "notes", "reviewed_at",
        ]

    def get_label(self, obj):
        from .models import PROIT_FIELD_CATALOG

        return PROIT_FIELD_CATALOG.get(obj.field_id, (obj.field_id,))[0]


class AIResearchRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResearchRun
        fields = [
            "id", "status", "started_at", "finished_at", "model", "searches_used", "tokens_in", "tokens_out",
            "summary", "error", "dropped",
        ]
