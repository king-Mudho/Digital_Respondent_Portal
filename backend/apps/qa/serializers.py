from rest_framework import serializers

from apps.kobo.models import QUANSubmission

from .models import QAEvent


class QAQueueSubmissionSerializer(serializers.ModelSerializer):
    sample_id = serializers.CharField(source="sample_case.sample_id", read_only=True)

    class Meta:
        model = QUANSubmission
        fields = [
            "id", "sample_id", "kobo_submission_uuid", "administration_mode",
            "qa_status", "submitted_at", "last_edited_at", "completion_seconds",
        ]


class QAEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = QAEvent
        fields = ["id", "submission", "kii_record", "document_record", "rule_triggered", "decision", "reviewer", "note", "created_at"]
        read_only_fields = ["id", "reviewer", "created_at"]


class QAExceptionSerializer(serializers.ModelSerializer):
    """One row of the daily exception queue. Carries enough context to act
    on the flag without opening the record it points at."""

    subject_type = serializers.SerializerMethodField()
    subject_ref = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True, default=None
    )
    resolved_by_username = serializers.CharField(
        source="resolved_by.username", read_only=True, default=None
    )
    age_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = QAEvent
        fields = [
            "id", "rule_triggered", "note", "created_at", "age_days",
            "subject_type", "subject_ref",
            "status", "assigned_to", "assigned_to_username",
            "resolution_note", "resolved_at", "resolved_by", "resolved_by_username",
        ]
        read_only_fields = fields

    def get_subject_type(self, obj) -> str:
        if obj.submission_id:
            return "QUAN submission"
        if obj.kii_record_id:
            return "KII record"
        if obj.document_record_id:
            return "Document"
        return "unknown"

    def get_subject_ref(self, obj) -> str | None:
        """The identifier a researcher would actually search for."""
        if obj.submission_id:
            return obj.submission.sample_case.sample_id
        if obj.kii_record_id:
            return obj.kii_record.kii_id
        if obj.document_record_id:
            return obj.document_record.document_id
        return None
