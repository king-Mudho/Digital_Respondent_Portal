"""Batch email invitations (apps/invitations/batch.py): the PI's and Field Coordinator's tool. Contact RAs keep
sending one invitation at a time from the case page; Supervisor may read."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin

from . import batch as b
from .models import InvitationBatch
from .tasks import send_invitation_batch


class InvitationBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitationBatch
        fields = ["id", "requested", "status", "sent", "failed", "skipped", "results", "error", "started_at", "finished_at"]


class InvitationBatchView(APIView):
    """GET /api/v1/invitations/batch/ -- what a batch would do now. POST {limit} -- start one (202)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        from apps.kobo.submission_copies import email_is_configured

        latest = InvitationBatch.objects.first()
        return Response({
            "email_configured": email_is_configured(),
            "candidates": b.batch_candidates().count(),
            "preview": b.preview(),
            "max_per_batch": b.per_batch_max(),
            "daily_max": b.daily_max(),
            "left_today": b.left_today(),
            "latest": InvitationBatchSerializer(latest).data if latest else None,
        })

    def post(self, request):
        try:
            limit = int(request.data.get("limit", 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            batch = b.start_batch(limit, user=request.user)
        except b.BatchError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        send_invitation_batch.delay(batch.pk)
        return Response(InvitationBatchSerializer(batch).data, status=202)


class InvitationBatchDetailView(APIView):
    """GET /api/v1/invitations/batch/{id}/ -- progress and results."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request, pk):
        return Response(InvitationBatchSerializer(get_object_or_404(InvitationBatch, pk=pk)).data)
