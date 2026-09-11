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
        read_only_fields = ["id", "ra"]


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["id", "sample_case", "kii_record", "scheduled_for", "mode", "status"]
        read_only_fields = ["id", "status"]
