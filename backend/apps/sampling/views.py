from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanViewSampleCases, IsFieldCoordinatorOrAdmin

from .models import Organisation, SampleCase, SampleType
from .serializers import (
    OrganisationSerializer,
    ReserveActivationSerializer,
    SampleCaseSerializer,
    WorkflowTransitionSerializer,
)
from .services import (
    InvalidMatchedCase,
    InvalidWorkflowTransition,
    activate_reserve,
    available_reserves_for,
    create_organisation,
    create_sample_case,
    resolve_stratum_for_organisation,
    set_matched_case,
    transition_workflow_status,
)


def _scope_to_assigned_cases_for_contact_ra(request, queryset):
    """Contact RA's "assigned cases" grant (docs/18) -- every other role
    that reaches this point (Field Coordinator/Admin/Supervisor) sees the
    unfiltered queryset; CanViewSampleCases has already refused write
    access for Contact RA, this only narrows *which* cases it can read."""
    role = getattr(getattr(request.user, "role", None), "name", None)
    if role == "CONTACT_RA":
        return queryset.filter(assigned_ra=request.user)
    return queryset


class SampleCaseListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/sample-cases/ -- list / import Main-400 & Reserve-400
    (docs/06_API_ARCHITECTURE.md). CanViewSampleCases: Contact RA and
    Supervisor get read-only (GET) access; only Field Coordinator/Admin can
    POST. Contact RA's GET is further scoped to its assigned cases only."""

    permission_classes = [CanViewSampleCases]
    serializer_class = SampleCaseSerializer
    filterset_fields = ["sample_type", "status", "workflow_status", "stratum__province"]
    search_fields = ["sample_id", "organisation__name", "organisation__master_id"]

    def get_queryset(self):
        queryset = SampleCase.objects.select_related("organisation", "stratum").order_by("sample_id")
        return _scope_to_assigned_cases_for_contact_ra(self.request, queryset)

    def create(self, request, *args, **kwargs):
        # A "stratum" is a derived grouping of the organisation's own
        # province/actor_family/size_class, not something worth
        # asking an admin to pick separately -- auto-resolve it (get-or-
        # create) when the caller doesn't supply one, so the "register
        # organisation + sample case" admin UI can skip that step entirely.
        data = dict(request.data)
        organisation_id = data.get("organisation")
        if not data.get("stratum") and organisation_id:
            organisation = get_object_or_404(Organisation, pk=organisation_id)
            data["stratum"] = resolve_stratum_for_organisation(organisation).id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # Sample_id/status/workflow_status must come from create_sample_case()
        # (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md) -- ModelSerializer's
        # default .create() would leave sample_id unset since it's read-only.
        case = create_sample_case(
            organisation=serializer.validated_data["organisation"],
            stratum=serializer.validated_data["stratum"],
            sample_type=serializer.validated_data["sample_type"],
            year=int(data["year"]) if data.get("year") else None,
        )
        return Response(SampleCaseSerializer(case).data, status=201)


class SampleCaseDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/sample-cases/{sample_id}/. Contact RA's GET is
    scoped to its assigned cases -- a case assigned to someone else 404s
    rather than 403s, so its existence isn't leaked either."""

    permission_classes = [CanViewSampleCases]
    serializer_class = SampleCaseSerializer
    lookup_field = "sample_id"

    def get_queryset(self):
        queryset = SampleCase.objects.select_related("organisation", "stratum", "matched_case")
        return _scope_to_assigned_cases_for_contact_ra(self.request, queryset)

    def perform_update(self, serializer):
        # matched_case must go through set_matched_case(), which validates
        # the pairing and writes the audit entry. A bare PATCH would let a
        # caller pair a Main to another Main, or hand one Reserve to two
        # Main cases -- silently breaking the reserve lock.
        if "matched_case" in serializer.validated_data:
            try:
                set_matched_case(
                    serializer.instance,
                    serializer.validated_data.pop("matched_case"),
                    changed_by=self.request.user,
                )
            except InvalidMatchedCase as exc:
                raise DRFValidationError({"matched_case": [str(exc)]}) from exc
        serializer.save()


class AvailableReservesView(APIView):
    """GET /api/v1/sample-cases/{sample_id}/available-reserves/ -- the
    Reserve cases this Main case may be paired with (still LOCKED, not
    already claimed by another Main), same stratum first. Backs the
    "Matched Reserve case" picker on the case detail page."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request, sample_id):
        main_case = get_object_or_404(
            SampleCase.objects.select_related("stratum"), sample_id=sample_id
        )
        if main_case.sample_type != SampleType.MAIN:
            return Response(
                {"error": {"code": "not_a_main_case", "message": "Only a MAIN case has a matched Reserve.", "field_errors": {}}},
                status=400,
            )

        candidates = available_reserves_for(main_case)[:200]
        return Response({"results": [
            {
                "id": c.id,
                "sample_id": c.sample_id,
                "organisation_name": c.organisation.name,
                "stratum_code": c.stratum.code,
                "same_stratum": c.stratum_id == main_case.stratum_id,
            }
            for c in candidates
        ]})


class OrganisationListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/organisations/ -- register a new organisation
    (Master_ID generated server-side, never user-entered) and list existing
    ones, e.g. for the "register organisation + sample case" admin UI."""

    permission_classes = [CanViewSampleCases]
    serializer_class = OrganisationSerializer
    filterset_fields = ["province", "actor_family", "size_class", "verification_status"]
    search_fields = ["name", "master_id", "district"]

    def get_queryset(self):
        return Organisation.objects.order_by("name")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organisation = create_organisation(**serializer.validated_data)
        return Response(OrganisationSerializer(organisation).data, status=201)


class ReserveActivateView(APIView):
    """POST /api/v1/sample-cases/{sample_id}/activate-reserve/ -- requires
    activation_reason (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, sample_id):
        try:
            reserve_case = SampleCase.objects.get(sample_id=sample_id)
        except SampleCase.DoesNotExist:
            return Response({"error": {"code": "not_found", "message": "No such SampleCase.", "field_errors": {}}}, status=404)

        serializer = ReserveActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            activated = activate_reserve(
                reserve_case,
                reason=serializer.validated_data["activation_reason"],
                activated_by=request.user,
                evidence_note=serializer.validated_data.get("activation_evidence_note", ""),
            )
        except ValueError as exc:
            return Response({"error": {"code": "activation_failed", "message": str(exc), "field_errors": {}}}, status=400)
        except ValidationError as exc:
            return Response({"error": {"code": "invalid_reason", "message": str(exc), "field_errors": {}}}, status=400)

        return Response(SampleCaseSerializer(activated).data)


class WorkflowTransitionView(APIView):
    """POST /api/v1/sample-cases/{sample_id}/transition/ -- the only sanctioned
    way to change a MAIN case's workflow_status. Routes through
    sampling.services.transition_workflow_status(), which validates the
    S00-S16 state machine and audit-logs a rejected attempt
    (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md, AGENTS.md ground rule 4).
    """

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, sample_id):
        sample_case = get_object_or_404(SampleCase, sample_id=sample_id)
        serializer = WorkflowTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = transition_workflow_status(
                sample_case, serializer.validated_data["workflow_status"], user=request.user
            )
        except InvalidWorkflowTransition as exc:
            return Response({"error": {"code": "invalid_transition", "message": str(exc), "field_errors": {}}}, status=400)

        return Response(SampleCaseSerializer(updated).data)
