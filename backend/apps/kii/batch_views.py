"""Batch KII invitations (apps/kii/batch.py, 2026-10-13): the PI's and Field Coordinator's tool, as for Main-400.
KII RAs send one invitation at a time from the record page; Supervisor may read."""

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin
from apps.invitations.batch import BatchError
from apps.invitations.batch_views import InvitationBatchSerializer, _channels
from apps.invitations.models import InvitationBatch
from apps.invitations.tasks import send_invitation_batch

from . import batch as kb


def _groups(raw) -> list[str]:
    if raw is None:
        return list(kb.GROUPS)
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(group).strip().upper() for group in raw if str(group).strip()]


def _flag(raw) -> bool:
    return str(raw).lower() in ("1", "true", "yes")


class KIIInvitationBatchView(APIView):
    """GET /api/v1/kii-invitations/batch/?channels=EMAIL&groups=CORE_60,RESERVE_30&named_only=1 -- what a batch with
    those choices would do now. POST {limit, channels, groups, named_only, mode} -- start one (202); mode "INTRO" sends
    the "ask first" introduction instead of the invitation."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        channels = [c for c in _channels(request.query_params.get("channels")) if c in kb.main.CHANNELS] or ["EMAIL"]
        groups = [g for g in _groups(request.query_params.get("groups")) if g in kb.GROUPS] or list(kb.GROUPS)
        latest = InvitationBatch.objects.filter(mode=kb.MODE).first()
        return Response({
            **kb.summary(channels, groups, named_only=_flag(request.query_params.get("named_only"))),
            "latest": InvitationBatchSerializer(latest).data if latest else None,
        })

    def post(self, request):
        try:
            limit = int(request.data.get("limit", 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            batch = kb.start_batch(limit, user=request.user, channels=_channels(request.data.get("channels")),
                                   groups=_groups(request.data.get("groups")), named_only=_flag(request.data.get("named_only")),
                                   intro=str(request.data.get("mode", "")).upper() == "INTRO")
        except BatchError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        send_invitation_batch.delay(batch.pk)
        return Response(InvitationBatchSerializer(batch).data, status=202)


class KIIInvitationBatchDetailView(APIView):
    """GET /api/v1/kii-invitations/batch/{id}/ -- progress and results."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request, pk):
        return Response(InvitationBatchSerializer(get_object_or_404(InvitationBatch, pk=pk, mode=kb.MODE)).data)
