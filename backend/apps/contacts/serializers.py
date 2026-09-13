from rest_framework import serializers

from .models import Appointment, ContactEvent, Respondent


class RespondentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Respondent
        fields = [
            "id", "full_name", "role_category", "is_eligible", "phone",
            "whatsapp_number", "email", "gatekeeper_name", "gatekeeper_contact",
        ]
        read_only_fields = ["id", "is_eligible"]


class ContactEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEvent
        fields = ["id", "sample_case", "channel", "occurred_at", "outcome", "notes", "next_action_date", "ra"]
        # sample_case is resolved from the URL's sample_id by
        # ContactEventListCreateView.perform_create(), never taken from the
        # request body -- read-only here so is_valid() doesn't reject a
        # caller for omitting a field it was never meant to supply.
        read_only_fields = ["id", "sample_case", "ra"]


class AppointmentSerializer(serializers.ModelSerializer):
    # The queue screen previously showed only the numeric FKs, so an RA
    # could not tell which case or informant an appointment belonged to.
    # Either FK may be null (an appointment is for one or the other).
    sample_id = serializers.SerializerMethodField()
    organisation_name = serializers.SerializerMethodField()
    kii_id = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id", "sample_case", "sample_id", "organisation_name",
            "kii_record", "kii_id", "scheduled_for", "mode", "status",
        ]
        read_only_fields = ["id", "status"]

    def get_sample_id(self, obj) -> str | None:
        return obj.sample_case.sample_id if obj.sample_case_id else None

    def get_organisation_name(self, obj) -> str | None:
        return obj.sample_case.organisation.name if obj.sample_case_id else None

    def get_kii_id(self, obj) -> str | None:
        return obj.kii_record.kii_id if obj.kii_record_id else None
