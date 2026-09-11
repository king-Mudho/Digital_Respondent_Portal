from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin
from api.throttling import PerTokenThrottle

from .services import (
    TokenNotInvitable,
    TokenValidationError,
    issue_invitation,
    revoke_token,
    validate_manual_code,
    validate_token,
)
from .models import InvitationToken


class InvitationValidateView(APIView):
    """GET /api/v1/invitations/validate/?t=<token> (or ?code=<manual_code>)
    -- public. Deliberately omits Sample_ID, stratum, Main/Reserve status,
    and any prior contact history (docs/06_API_ARCHITECTURE.md, AGENTS.md
    ground rule 6)."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, AnonRateThrottle]

    def get(self, request):
        raw_token = request.query_params.get("t")
        raw_code = request.query_params.get("code")

        try:
            if raw_token:
                token = validate_token(raw_token)
            elif raw_code:
                token = validate_manual_code(raw_code)
            else:
                return Response(
                    {"error": {"code": "token_missing", "message": "A token or code is required.", "field_errors": {}}},
                    status=400,
                )
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        org_name = token.sample_case.organisation.name
        return Response({
            "status": "valid",
            "organisation_name_confirmation": f"Please confirm: is this {org_name}?",
            "requires_eligibility_check": True,
        })


class InvitationIssueView(APIView):
    """POST /api/v1/invitations/ -- internal. Issue a new invitation token
    for a SampleCase; is_invitable() enforcement happens inside
    invitations.services.issue_invitation (AGENTS.md ground rule 4)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request):
        from apps.sampling.models import SampleCase

        sample_id = request.data.get("sample_id")
        channel = request.data.get("channel", "WHATSAPP")
        invitation_wave = int(request.data.get("invitation_wave", 1))

        try:
            sample_case = SampleCase.objects.get(sample_id=sample_id)
        except SampleCase.DoesNotExist:
            return Response(
                {"error": {"code": "sample_case_not_found", "message": "No such SampleCase.", "field_errors": {}}},
                status=404,
            )

        try:
            raw_token, raw_code, token = issue_invitation(
                sample_case, channel=channel, invitation_wave=invitation_wave, issued_by=request.user
            )
        except TokenNotInvitable as exc:
            return Response({"error": {"code": "not_invitable", "message": str(exc), "field_errors": {}}}, status=403)

        return Response({
            "token_id": token.id,
            "raw_token": raw_token,
            "raw_manual_code": raw_code,
            "expires_at": token.expires_at,
        }, status=201)


class InvitationRevokeView(APIView):
    """POST /api/v1/invitations/{token_id}/revoke/ -- internal."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, token_id):
        try:
            token = InvitationToken.objects.get(pk=token_id)
        except InvitationToken.DoesNotExist:
            return Response({"error": {"code": "not_found", "message": "No such token.", "field_errors": {}}}, status=404)

        reason = request.data.get("reason", "")
        revoke_token(token, reason, revoked_by=request.user)
        return Response({"status": "revoked"})
