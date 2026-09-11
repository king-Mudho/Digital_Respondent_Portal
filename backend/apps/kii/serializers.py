from rest_framework import serializers

from .models import KIIRecord


class KIIRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = KIIRecord
        fields = [
            "id", "kii_id", "stakeholder_category", "organisation", "participant_name",
            "participant_role", "status", "preferred_mode", "interview_date",
            "duration_minutes", "interviewer", "transcript_status", "coding_status",
            "thematic_coverage_tags",
        ]
        read_only_fields = ["id", "kii_id"]
