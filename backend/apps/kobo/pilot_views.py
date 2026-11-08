from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanViewPilot


def _error(exc, status=400):
    return Response({"error": {"code": "pilot_error", "message": str(exc), "field_errors": {}}}, status=status)


class PilotListView(APIView):
    """GET /api/v1/pilot/?strand=QUAN|KII|DOCUMENT&show=flagged|excluded -- the ZAS 2026 pilot records (2026-11-08):
    totals per form, the counts the dashboards add, and each record's non-identifying summary, flags and whether it is
    counted. Never the answers themselves."""

    permission_classes = [CanViewPilot]

    def get(self, request):
        from .pilot import listing

        return Response(listing(strand=request.query_params.get("strand", ""), show=request.query_params.get("show", "")))


class PilotSyncView(APIView):
    """POST /api/v1/pilot/sync/ -- copy the pilot forms' submissions from KoboToolbox again (PI). Keeps every
    include/exclude decision already made."""

    permission_classes = [CanViewPilot]

    def post(self, request):
        from .pilot import PilotError, sync

        try:
            return Response({"synced": sync(user=request.user)})
        except PilotError as exc:
            return _error(exc, 502)


class PilotDecisionView(APIView):
    """POST /api/v1/pilot/<id>/decision/ {included, reason} -- the PI counts or leaves out one pilot record; a reason
    is required to leave one out. Audited."""

    permission_classes = [CanViewPilot]

    def post(self, request, pk):
        from .pilot import PilotError, decide

        try:
            record = decide(request.user, pk, included=bool(request.data.get("included")),
                            reason=str(request.data.get("reason", "")))
        except PilotError as exc:
            return _error(exc)
        return Response({"id": record.pk, "included": record.included, "exclusion_reason": record.exclusion_reason})
