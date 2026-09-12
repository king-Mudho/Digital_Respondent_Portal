from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin

from .models import SampleCase
from .serializers import ReserveActivationSerializer, SampleCaseSerializer, WorkflowTransitionSerializer
from .services import InvalidWorkflowTransition, activate_reserve, transition_workflow_status


class SampleCaseListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/sample-cases/ -- list / import Main-400 & Reserve-400
    (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = SampleCaseSerializer
    filterset_fields = ["sample_type", "status", "workflow_status", "stratum__province"]

    def get_queryset(self):
        return SampleCase.objects.select_related("organisation", "stratum").order_by("sample_id")


class SampleCaseDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/sample-cases/{sample_id}/."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = SampleCaseSerializer
    lookup_field = "sample_id"
    queryset = SampleCase.objects.select_related("organisation", "stratum")


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
