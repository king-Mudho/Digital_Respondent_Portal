from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsQAOrAdmin
from apps.kobo.models import QAStatus, QUANSubmission

from .models import QADecision
from .serializers import QAQueueSubmissionSerializer
from .services import record_human_decision


class QAQueueView(ListAPIView):
    """GET /api/v1/qa/queue/ -- submissions pending a human QA decision
    (docs/06_API_ARCHITECTURE.md). Scoped to QUANSubmission for now; KII/
    documentary-evidence queue items are added in Phase 7 alongside those
    apps' full workflow wiring.
    """

    permission_classes = [IsQAOrAdmin]
    serializer_class = QAQueueSubmissionSerializer

    def get_queryset(self):
        return QUANSubmission.objects.filter(
            qa_status__in=[QAStatus.PENDING, QAStatus.QUERY]
        ).select_related("sample_case").order_by("submitted_at")


class QASubmissionDecisionView(APIView):
    """POST /api/v1/qa/submission/{id}/decision/ -- record a human QA
    decision. A mandatory note is enforced in qa.services.record_human_decision
    (docs/15_QA_AND_DATA_QUALITY.md)."""

    permission_classes = [IsQAOrAdmin]

    def post(self, request, pk):
        submission = get_object_or_404(QUANSubmission, pk=pk)
        decision = request.data.get("decision")
        note = request.data.get("note", "")

        if decision not in QADecision.values:
            return Response(
                {"error": {"code": "invalid_decision", "message": "decision must be one of ACCEPT/QUERY/REJECT.", "field_errors": {}}},
                status=400,
            )
        try:
            event = record_human_decision(
                submission=submission, reviewer=request.user, decision=decision, note=note
            )
        except ValueError as exc:
            return Response({"error": {"code": "note_required", "message": str(exc), "field_errors": {}}}, status=400)

        return Response({"id": event.id, "decision": event.decision, "qa_status": submission.qa_status})
