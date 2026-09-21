from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsQAOrAdmin
from apps.accounts.models import User
from apps.kobo.models import QAStatus, QUANSubmission
from apps.proit.services import ReconciliationRequired

from .models import QADecision, QAEvent
from .serializers import QAExceptionSerializer, QAQueueSubmissionSerializer
from .services import (
    InvalidExceptionTransition,
    assign_exception,
    open_exceptions,
    record_human_decision,
    resolve_exception,
)


def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


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


class QAExceptionQueueView(ListAPIView):
    """GET /api/v1/qa/exceptions/ -- the daily exception queue
    (ResearchOS brief A6: "daily exception queue with owner/status").

    Open and in-progress flags by default, oldest first, because this is a
    backlog rather than a feed. `?mine=1` narrows to the caller's own,
    `?include_resolved=1` shows closed ones too.
    """

    permission_classes = [IsQAOrAdmin]
    serializer_class = QAExceptionSerializer
    filterset_fields = ["status", "rule_triggered"]

    def get_queryset(self):
        return open_exceptions(
            assigned_to=self.request.user if self.request.query_params.get("mine") else None,
            include_resolved=bool(self.request.query_params.get("include_resolved")),
        )


class QAExceptionAssignView(APIView):
    """POST /api/v1/qa/exceptions/{id}/assign/ -- {"assigned_to": <user id|null>}.
    Assigning moves the flag to IN_PROGRESS; passing null releases it."""

    permission_classes = [IsQAOrAdmin]

    def post(self, request, pk):
        event = get_object_or_404(QAEvent, pk=pk)
        raw = request.data.get("assigned_to", None)
        assignee = None
        if raw not in (None, "", "null"):
            assignee = User.objects.filter(pk=raw, is_active=True).first()
            if assignee is None:
                return _error("unknown_user", "No such active user.")
        try:
            assign_exception(event, assignee=assignee, changed_by=request.user)
        except InvalidExceptionTransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(QAExceptionSerializer(event).data)


class QAExceptionResolveView(APIView):
    """POST /api/v1/qa/exceptions/{id}/resolve/ --
    {"status": "RESOLVED"|"DISMISSED", "note": "..."}. The note is mandatory:
    a closure nobody explained is indistinguishable from one nobody looked at."""

    permission_classes = [IsQAOrAdmin]

    def post(self, request, pk):
        event = get_object_or_404(QAEvent, pk=pk)
        try:
            resolve_exception(
                event,
                status=request.data.get("status", ""),
                note=request.data.get("note", ""),
                resolved_by=request.user,
            )
        except InvalidExceptionTransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(QAExceptionSerializer(event).data)


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
        except ReconciliationRequired as exc:
            return _error("reconciliation_required", str(exc), 409)
        except ValueError as exc:
            return Response({"error": {"code": "note_required", "message": str(exc), "field_errors": {}}}, status=400)

        return Response({"id": event.id, "decision": event.decision, "qa_status": submission.qa_status})
