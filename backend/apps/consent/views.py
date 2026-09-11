from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from api.throttling import PerTokenThrottle
from apps.invitations.models import TokenStatus
from apps.invitations.services import TokenValidationError, advance_token_status, validate_token

from .models import ConsentDecision, ConsentType
from .services import record_consent


class ConsentSubmitView(APIView):
    """POST /api/v1/consent/ -- public, scoped to the single SampleCase
    resolved from the token (docs/06_API_ARCHITECTURE.md). Explicit opt-in
    action required (docs/10_INVITATION_AND_CONSENT.md)."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, AnonRateThrottle]

    def post(self, request):
        raw_token = request.data.get("token", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        consent_type = request.data.get("consent_type", ConsentType.PARTICIPATION)
        decision = request.data.get("decision")
        information_sheet_version = request.data.get("information_sheet_version", "")
        method = request.data.get("method")

        if consent_type not in ConsentType.values or decision not in ConsentDecision.values:
            return Response(
                {"error": {"code": "invalid_input", "message": "Invalid consent_type or decision.", "field_errors": {}}},
                status=400,
            )

        record = record_consent(
            sample_case=token.sample_case,
            consent_type=consent_type,
            decision=decision,
            information_sheet_version=information_sheet_version,
            method=method,
        )

        if consent_type == ConsentType.PARTICIPATION and decision == ConsentDecision.GIVEN:
            advance_token_status(token, TokenStatus.CONSENTED)

        return Response({"id": record.id, "consent_type": record.consent_type, "decision": record.decision})
