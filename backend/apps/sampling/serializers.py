from rest_framework import serializers

from .models import Organisation, SampleCase


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = [
            "id", "master_id", "name", "entity_type", "province", "district",
            "actor_family", "value_chain", "size_class", "verification_status",
        ]
        read_only_fields = ["id", "master_id"]


class SampleCaseSerializer(serializers.ModelSerializer):
    organisation_name = serializers.CharField(source="organisation.name", read_only=True)
    organisation_master_id = serializers.CharField(source="organisation.master_id", read_only=True)
    stratum_code = serializers.CharField(source="stratum.code", read_only=True)

    class Meta:
        model = SampleCase
        fields = [
            "id", "sample_id", "organisation", "organisation_name", "organisation_master_id",
            "stratum", "stratum_code", "sample_type", "matched_case", "status",
            "workflow_status", "activation_reason", "activated_by", "activated_at",
            "activation_evidence_note",
        ]
        read_only_fields = [
            "id", "sample_id", "activated_by", "activated_at",
        ]


class ReserveActivationSerializer(serializers.Serializer):
    activation_reason = serializers.CharField()
    activation_evidence_note = serializers.CharField(required=False, allow_blank=True)
