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
    assigned_ra_username = serializers.CharField(source="assigned_ra.username", read_only=True, default=None)

    class Meta:
        model = SampleCase
        fields = [
            "id", "sample_id", "organisation", "organisation_name", "organisation_master_id",
            "stratum", "stratum_code", "sample_type", "matched_case", "status",
            "workflow_status", "activation_reason", "activated_by", "activated_at",
            "activation_evidence_note", "assigned_ra", "assigned_ra_username",
        ]
        # status/workflow_status/activation_* are read-only here on purpose: they
        # must only ever change through sampling.services.transition_workflow_status()
        # or activate_reserve() (SampleCaseTransitionView / ReserveActivateView),
        # never a bare PATCH -- both validate the S00-S16 state machine and the
        # five-authorised-reasons rule, and both write an AuditEvent. A bug found
        # during the Sep 2026 hardening pass: this PATCH endpoint let a caller jump
        # a case straight from S00 to S11 with no validation and no audit trail at
        # all (confirmed by a reproducing test before this fix).
        read_only_fields = [
            "id", "sample_id", "status", "workflow_status", "activation_reason",
            "activated_by", "activated_at", "activation_evidence_note",
        ]


class ReserveActivationSerializer(serializers.Serializer):
    activation_reason = serializers.CharField()
    activation_evidence_note = serializers.CharField(required=False, allow_blank=True)


class WorkflowTransitionSerializer(serializers.Serializer):
    workflow_status = serializers.CharField()
