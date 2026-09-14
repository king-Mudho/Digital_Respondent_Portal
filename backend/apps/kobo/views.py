from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsQAOrAdmin
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.invitations.models import TokenStatus
from apps.invitations.services import TokenValidationError, advance_token_status, validate_token
from apps.sampling.models import WorkflowStatus
from apps.sampling.services import advance_case_on_respondent_event

from .models import ReconciliationLog, ReconciliationTrigger
from .services import (
    KoboNotConfigured,
    KoboRedirectDenied,
    build_redirect_url,
    reconcile,
    reconciliation_is_configured,
)
from .tasks import reconcile_kobo_submissions


class KoboRedirectURLView(APIView):
    """GET /api/v1/kobo/redirect-url/?t=<token> -- public, scoped to the
    single SampleCase resolved from the validated token
    (docs/06_API_ARCHITECTURE.md "Security")."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        raw_token = request.query_params.get("t", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        try:
            payload = build_redirect_url(
                token.sample_case,
                token_id=token.id,
                invitation_wave=token.invitation_wave,
                administration_mode=request.query_params.get("administration_mode", "01"),
                respondent_role_category=request.query_params.get("respondent_role_category", ""),
                consent_version=request.query_params.get("consent_version", ""),
                ra_id=request.query_params.get("ra_id", ""),
            )
        except KoboRedirectDenied as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=403)
        except KoboNotConfigured as exc:
            # 503, not a broken link: the respondent flow turns this into
            # "not open yet" with an assisted-completion route.
            return Response(
                {"error": {"code": "questionnaire_unavailable", "message": str(exc), "field_errors": {}}},
                status=503,
            )

        # The questionnaire link is being handed over: the survey has started.
        advance_token_status(token, TokenStatus.SURVEY_STARTED)
        advance_case_on_respondent_event(token.sample_case, WorkflowStatus.S07_SURVEY_STARTED)
        return Response(payload)


class KoboWebhookView(APIView):
    """POST /api/v1/kobo/webhook/ -- Kobo REST Services target. Validates the
    shared-secret header and only ever enqueues an early reconciliation run;
    the payload is never written directly to QUANSubmission
    (docs/08_BACKEND_ARCHITECTURE.md, docs/11_KOBOTOOLBOX_INTEGRATION.md)."""

    permission_classes = [AllowAny]

    def post(self, request):
        shared_secret = request.headers.get("X-Kobo-Shared-Secret", "")
        if not settings.KOBO_WEBHOOK_SHARED_SECRET or shared_secret != settings.KOBO_WEBHOOK_SHARED_SECRET:
            return Response({"error": {"code": "invalid_secret", "message": "Invalid shared secret.", "field_errors": {}}}, status=403)

        reconcile_kobo_submissions.delay(triggered_by=ReconciliationTrigger.WEBHOOK_HEADSUP)
        return Response({"status": "reconciliation_triggered"}, status=202)


def _serialize_log(log):
    return {
        "id": log.pk,
        "run_started_at": log.run_started_at,
        "run_finished_at": log.run_finished_at,
        "submissions_pulled": log.submissions_pulled,
        "new_submissions": log.new_submissions,
        "updated_submissions": log.updated_submissions,
        "mismatches_flagged": log.mismatches_flagged,
        "triggered_by": log.triggered_by,
        "error_message": log.error_message,
    }


class KoboReconcileView(APIView):
    """POST /api/v1/kobo/reconcile/ -- internal manual trigger ("Sync now");
    calls the same service function the scheduled job calls. Returns 502
    (not 200) when the Kobo API call itself failed, so the admin UI can
    distinguish "ran, found nothing new" from "couldn't reach Kobo".

    IsQAOrAdmin, not IsFieldCoordinatorOrAdmin: the Sync panel lives on the
    QA queue screen, and the QUAN QA RA -- whose job Kobo ingestion is --
    got a 403 from the button in front of them (fixed 2026-09-14)."""

    permission_classes = [IsQAOrAdmin]

    def post(self, request):
        try:
            log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)
        except KoboNotConfigured as exc:
            return Response(
                {"error": {"code": "kobo_not_configured", "message": str(exc), "field_errors": {}}},
                status=503,
            )
        if log.error_message:
            return Response(
                {"error": {"code": "kobo_unreachable", "message": log.error_message, "field_errors": {}}},
                status=502,
            )
        return Response(_serialize_log(log))


class KoboReconciliationStatusView(APIView):
    """GET /api/v1/kobo/reconciliation-status/ -- the most recent
    reconciliation run (scheduled or manual), so the admin UI can show when
    Kobo was last synced and surface a failed run without an admin having to
    trigger one themselves to find out.

    Returns {"configured": bool, "last_run": <run>|null}. `configured` is
    separate so an unconnected form reads as "not connected yet" rather
    than as the most recent failure."""

    permission_classes = [IsQAOrAdmin]

    def get(self, request):
        log = ReconciliationLog.objects.order_by("-run_started_at").first()
        return Response({
            "configured": reconciliation_is_configured(),
            "last_run": _serialize_log(log) if log is not None else None,
        })
