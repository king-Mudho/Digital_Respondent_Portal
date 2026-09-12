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
    class Meta:
        model = Appointment
        fields = ["id", "sample_case", "kii_record", "scheduled_for", "mode", "status"]
        read_only_fields = ["id", "status"]
