from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin
from api.throttling import PerTokenThrottle
from apps.invitations.services import TokenValidationError, validate_token

from .models import ReconciliationLog, ReconciliationTrigger
from .services import KoboRedirectDenied, build_redirect_url, reconcile
from .tasks import reconcile_kobo_submissions


class KoboRedirectURLView(APIView):
    """GET /api/v1/kobo/redirect-url/?t=<token> -- public, scoped to the
    single SampleCase resolved from the validated token
    (docs/06_API_ARCHITECTURE.md "Security")."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, AnonRateThrottle]

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
    distinguish "ran, found nothing new" from "couldn't reach Kobo"."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request):
        log = reconcile(triggered_by=ReconciliationTrigger.MANUAL)
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
    trigger one themselves to find out."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        log = ReconciliationLog.objects.order_by("-run_started_at").first()
        if log is None:
            return Response(None)
        return Response(_serialize_log(log))
