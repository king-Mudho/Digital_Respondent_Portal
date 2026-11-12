"""Calls screen endpoints (apps/contacts/calls.py, 2026-10-25)."""

from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanUseCalls

from .calls import CallError, call_list, log_call


def _error(exc: CallError) -> Response:
    return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)


class CallListView(APIView):
    """GET /api/v1/calls/?study=all|main|kii&stage=all|started|consented|opened|not_opened&q=&said_yes=1 -- everyone
    whose link was sent but who has not finished, closest to finishing first, with every contact on file; said_yes=1
    keeps those who answered YES to the introduction and were sent their link for it. Rows are scoped to
    what this user may see (a Contact RA their assigned cases, a KII RA the KII records)."""

    permission_classes = [CanUseCalls]

    def get(self, request):
        p = request.query_params
        study = p.get("study", "all") if p.get("study") in ("all", "main", "kii") else "all"
        return Response(call_list(request.user, study=study, stage=p.get("stage", "all"), q=p.get("q", ""),
                                  said_yes=p.get("said_yes") in ("1", "true")))


class CallLogView(APIView):
    """POST /api/v1/calls/{main|kii}/{SID-.../KII-...}/ {outcome, notes, next_action_date, channel} -- records one call
    in the case's or record's contact-attempt log: channel PHONE (the default), WHATSAPP_CALL or WHATSAPP_VIDEO.
    Supervisor is read-only (CanUseCalls)."""

    permission_classes = [CanUseCalls]

    def post(self, request, kind, ident):
        d = request.data
        try:
            event = log_call(request.user, kind, ident, outcome=d.get("outcome", ""), notes=d.get("notes", ""),
                             next_action_date=d.get("next_action_date") or None,
                             channel=str(d.get("channel") or "PHONE"))
        except CallError as exc:
            return _error(exc)
        return Response({"id": event.pk, "outcome": event.outcome, "occurred_at": event.occurred_at.isoformat()}, status=201)
