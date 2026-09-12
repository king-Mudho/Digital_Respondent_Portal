from rest_framework import serializers

from .models import KIIRecord


class KIIRecordSerializer(serializers.ModelSerializer):
    # Surfaces the current decision (or None if never recorded) so the admin
    # UI can show whether consent was already captured for this KII, rather
    # than the RA having no way to tell short of re-clicking "record" and
    # creating a duplicate ConsentRecord row.
    participation_consent_decision = serializers.CharField(
        source="participation_consent.decision", read_only=True, default=None
    )
    recording_consent_decision = serializers.CharField(
        source="recording_consent.decision", read_only=True, default=None
    )

    class Meta:
        model = KIIRecord
        fields = [
            "id", "kii_id", "stakeholder_category", "organisation", "participant_name",
            "participant_role", "status", "preferred_mode", "interview_date",
            "duration_minutes", "interviewer", "transcript_status", "coding_status",
            "thematic_coverage_tags", "participation_consent_decision", "recording_consent_decision",
        ]
        read_only_fields = ["id", "kii_id"]
