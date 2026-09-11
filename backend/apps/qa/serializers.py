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
