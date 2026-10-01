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


class OrganisationUpdateSerializer(serializers.ModelSerializer):
    """Correcting an already-saved organisation (OrganisationDetailView PATCH) --
    deliberately narrower than OrganisationSerializer. province/actor_family/
    size_class are read-only here even though OrganisationSerializer allows
    writing them at creation: sampling.services.resolve_stratum_for_organisation()
    resolves a case's StratumDefinition from these three fields once, at
    SampleCase creation, and never re-resolves it afterwards. Allowing a later
    edit here would silently detach an organisation from the stratum its
    existing case was paired and Reserve-matched against -- the Main-400/
    Reserve-400 integrity AGENTS.md ground rule 4 treats as database-enforced,
    not a UI convenience. The province code is also baked into the immutable
    master_id. verification_status is likewise excluded: it has its own
    verify flow (sampling.services bulk verification), not a bare field edit."""

    class Meta:
        model = Organisation
        fields = [
            "id", "master_id", "name", "entity_type", "province", "district",
            "actor_family", "value_chain", "size_class", "verification_status",
        ]
        read_only_fields = [
            "id", "master_id", "province", "actor_family", "size_class", "verification_status",
        ]


class SampleCaseSerializer(serializers.ModelSerializer):
    organisation_name = serializers.CharField(source="organisation.name", read_only=True)
    organisation_master_id = serializers.CharField(source="organisation.master_id", read_only=True)
    stratum_code = serializers.CharField(source="stratum.code", read_only=True)
    assigned_ra_username = serializers.CharField(source="assigned_ra.username", read_only=True, default=None)
    # So the case detail page can show which Reserve backs this case up
    # without a second request per row.
    matched_case_sample_id = serializers.CharField(
        source="matched_case.sample_id", read_only=True, default=None
    )
    matched_case_organisation_name = serializers.CharField(
        source="matched_case.organisation.name", read_only=True, default=None
    )

    class Meta:
        model = SampleCase
        fields = [
            "id", "sample_id", "organisation", "organisation_name", "organisation_master_id",
            "stratum", "stratum_code", "sample_type", "matched_case",
            "matched_case_sample_id", "matched_case_organisation_name", "status",
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
        #
        # organisation/stratum/sample_type are deliberately NOT listed here even
        # though a bare PATCH to them is just as dangerous (it could silently
        # reassign a Sample ID to a different organisation, or flip MAIN/RESERVE,
        # with no validation and no audit trail) -- this same serializer is also
        # used by SampleCaseListCreateView.create(), which needs these three in
        # validated_data to build the case in the first place. Making them
        # read-only here would make that KeyError on every creation. See
        # SampleCaseDetailView.perform_update(), which pops them out of
        # validated_data on PATCH only, the same way it already does matched_case.
        read_only_fields = [
            "id", "sample_id", "status", "workflow_status", "activation_reason",
            "activated_by", "activated_at", "activation_evidence_note",
        ]


class ReserveActivationSerializer(serializers.Serializer):
    activation_reason = serializers.CharField()
    activation_evidence_note = serializers.CharField(required=False, allow_blank=True)


class WorkflowTransitionSerializer(serializers.Serializer):
    workflow_status = serializers.CharField()
