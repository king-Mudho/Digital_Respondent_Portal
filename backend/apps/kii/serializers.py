from rest_framework import serializers

from .models import KIIRecord
from .services import build_kii_coding_url, kii_form_is_configured


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
    # kii_form_configured / coding_url are split so the frontend can tell
    # apart "nobody has set KOBO_KII_FORM_URL yet" from "it's set up, but
    # this person hasn't consented yet" -- two different messages, two
    # different people who can fix it.
    kii_form_configured = serializers.SerializerMethodField()
    coding_url = serializers.SerializerMethodField()

    class Meta:
        model = KIIRecord
        fields = [
            "id", "kii_id", "stakeholder_category", "organisation", "participant_name",
            "participant_role", "status", "preferred_mode", "interview_date",
            "duration_minutes", "interviewer", "transcript_status", "coding_status",
            "thematic_coverage_tags", "participation_consent_decision", "recording_consent_decision",
            "kii_form_configured", "coding_url",
        ]
        read_only_fields = ["id", "kii_id", "kii_form_configured", "coding_url"]

    def _is_list_context(self) -> bool:
        # build_kii_coding_url() calls has_given_consent(), which always
        # issues a fresh ConsentRecord query (apps/consent/services.py
        # latest_consent -- select_related on participation_consent doesn't
        # help, since it re-queries by kii_record rather than following that
        # FK). Computing it for every row of the KII register would put back
        # exactly the one-query-per-row growth the register was fixed for
        # (README "Per-row queries" -- test_kii_register_queries_do_not_grow_
        # with_rows). Only the single-record detail page needs this field;
        # `self.parent` is the ListSerializer when DRF is rendering a list.
        return isinstance(self.parent, serializers.ListSerializer)

    def get_kii_form_configured(self, obj):
        if self._is_list_context():
            return None
        return kii_form_is_configured()

    def get_coding_url(self, obj):
        if self._is_list_context():
            return None
        return build_kii_coding_url(obj)
