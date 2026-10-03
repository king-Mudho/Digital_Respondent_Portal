from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageKII
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import has_given_consent, record_consent
from apps.invitations.messages import portal_base
from apps.kobo.submission_copies import email_is_configured

from .messages import KIIInvitationSendError, build_kii_messages, email_kii_invitation, kii_recipients
from .models import KIIInvitationToken, KIIRecord, KIIStatus
from .serializers import KIIInvitationTokenSerializer, KIIRecordSerializer
from .services import (
    InvalidKIITransition,
    KIIRecordingConsentRequired,
    KIITokenValidationError,
    advance_coding_status,
    advance_transcript_status,
    generate_kii_id,
    issue_kii_invitation,
    kii_form_is_configured,
    mark_completed,
    revoke_kii_invitation,
    transition_kii_status,
    validate_kii_manual_code,
    validate_kii_token,
)


class KIIRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/kii/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [CanManageKII]
    serializer_class = KIIRecordSerializer
    filterset_fields = ["status", "stakeholder_category", "transcript_status", "coding_status"]
    search_fields = [
        "kii_id", "participant_name", "participant_role",
        "stakeholder_category", "organisation__name",
    ]
    # KIIRecord has no Meta.ordering -- an unordered queryset makes
    # PageNumberPagination's page boundaries arbitrary, so a record can
    # appear on two pages or on none.
    queryset = KIIRecord.objects.select_related("participation_consent", "recording_consent").order_by("kii_id")

    def perform_create(self, serializer):
        serializer.save(kii_id=generate_kii_id())


class KIIRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [CanManageKII]
    serializer_class = KIIRecordSerializer
    queryset = KIIRecord.objects.select_related("participation_consent", "recording_consent")


def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


class KIIStatusTransitionView(APIView):
    """POST /api/v1/kii/{id}/status/ -- {"status": "SCHEDULED"|"COMPLETED"|...}.
    Completing with with_recording=true requires separate recording consent
    (AGENTS.md ground rule 6)."""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        new_status = request.data.get("status")
        with_recording = bool(request.data.get("with_recording", False))

        try:
            if new_status == KIIStatus.COMPLETED:
                mark_completed(record, with_recording=with_recording)
            else:
                transition_kii_status(record, new_status)
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        except KIIRecordingConsentRequired as exc:
            return _error("recording_consent_required", str(exc), status=403)

        return Response(KIIRecordSerializer(record).data)


class KIIConsentView(APIView):
    """POST /api/v1/kii/{id}/consent/ -- records participation or recording
    consent, always as a separate row per consent_type."""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        consent_type = request.data.get("consent_type")
        decision = request.data.get("decision")
        if consent_type not in ConsentType.values or decision not in ConsentDecision.values:
            return _error("invalid_input", "Invalid consent_type or decision.")

        consent_record = record_consent(
            kii_record=record,
            consent_type=consent_type,
            decision=decision,
            information_sheet_version=request.data.get("information_sheet_version", ""),
            method=request.data.get("method", ConsentMethod.VERBAL_RA_RECORDED),
        )

        if consent_type == ConsentType.PARTICIPATION:
            record.participation_consent = consent_record
            record.save(update_fields=["participation_consent"])
        elif consent_type == ConsentType.KII_RECORDING:
            record.recording_consent = consent_record
            record.save(update_fields=["recording_consent"])

        return Response({"id": consent_record.id, "consent_type": consent_record.consent_type, "decision": consent_record.decision})


class KIITranscriptStatusView(APIView):
    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        try:
            advance_transcript_status(record, request.data.get("transcript_status"))
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(KIIRecordSerializer(record).data)


class KIICodingStatusView(APIView):
    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        try:
            advance_coding_status(record, request.data.get("coding_status"))
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(KIIRecordSerializer(record).data)


# --- KII self-service invitation (2026-10-01) --------------------------------
#
# Public, token-gated respondent-facing endpoints mirroring apps.invitations.
# views -- see apps/kii/services.py and apps/kii/messages.py for why this is a
# parallel surface rather than an extension of the Main-400 one.

class KIIInvitationValidateView(APIView):
    """GET /api/v1/kii-invitations/validate/?t=<token> (or ?code=) -- public.
    Unlike the Main-400 equivalent, it's safe to return the participant's own
    name: the message they received was already addressed to them by name,
    and this is a known individual the research team identified, not an
    anonymous organisation being confirmed."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        raw_token = request.query_params.get("t")
        raw_code = request.query_params.get("code")
        try:
            if raw_token:
                token = validate_kii_token(raw_token)
            elif raw_code:
                token = validate_kii_manual_code(raw_code)
            else:
                return _error("token_missing", "A token or code is required.")
        except KIITokenValidationError as exc:
            return _error(exc.code, str(exc))

        return Response({"status": "valid", "participant_name": token.kii_record.participant_name})


class KIIInvitationIssueView(APIView):
    """GET /api/v1/kii-invitations/?kii_id=<id> -- invitation history.
    POST /api/v1/kii-invitations/ -- issue a new self-service token."""

    permission_classes = [CanManageKII]

    def get(self, request):
        kii_id = request.query_params.get("kii_id")
        if not kii_id:
            return _error("kii_id_required", "kii_id is required.")
        tokens = KIIInvitationToken.objects.filter(kii_record__kii_id=kii_id).order_by("-issued_at")
        return Response({"results": KIIInvitationTokenSerializer(tokens, many=True).data})

    def post(self, request):
        kii_id = request.data.get("kii_id")
        channel = request.data.get("channel", "WHATSAPP")
        record = get_object_or_404(KIIRecord, kii_id=kii_id)

        raw_token, raw_code, token = issue_kii_invitation(record, channel=channel, issued_by=request.user)

        link = f"{portal_base(request.data.get('link_base'))}/ki/{raw_token}"
        who = kii_recipients(record)
        return Response({
            "token_id": token.id,
            "raw_token": raw_token,
            "raw_manual_code": raw_code,
            "expires_at": token.expires_at,
            "link": link,
            **who,
            "email_configured": email_is_configured(),
            "messages": build_kii_messages(kii_record=record, link=link, manual_code=raw_code, expires_at=token.expires_at),
        }, status=201)


class KIIInvitationEmailView(APIView):
    """POST /api/v1/kii-invitations/{token_id}/send-email/ {link, manual_code}."""

    permission_classes = [CanManageKII]

    def post(self, request, token_id):
        token = get_object_or_404(KIIInvitationToken.objects.select_related("kii_record"), pk=token_id)
        try:
            result = email_kii_invitation(token, link=str(request.data.get("link", "")),
                                          manual_code=str(request.data.get("manual_code", "")), user=request.user)
        except KIIInvitationSendError as exc:
            return _error(exc.code, str(exc), status=exc.status)
        except Exception as exc:  # SMTP refused, timed out, ...
            return _error("email_failed", f"The email could not be sent ({exc.__class__.__name__}).", status=502)
        return Response(result)


class KIIInvitationRevokeView(APIView):
    """POST /api/v1/kii-invitations/{token_id}/revoke/."""

    permission_classes = [CanManageKII]

    def post(self, request, token_id):
        token = get_object_or_404(KIIInvitationToken, pk=token_id)
        revoke_kii_invitation(token, request.data.get("reason", ""), revoked_by=request.user)
        return Response({"status": "revoked"})


class KIIConsentSubmitView(APIView):
    """POST /api/v1/kii-consent/ {token, decision, information_sheet_version} --
    public, scoped to the single KIIRecord resolved from the token. Always
    PARTICIPATION consent recorded by web clickthrough -- unlike the staff-
    facing KIIConsentView, there's exactly one consent type and one method
    here, since nobody is present to record anything else."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def post(self, request):
        raw_token = request.data.get("token", "")
        try:
            token = validate_kii_token(raw_token)
        except KIITokenValidationError as exc:
            return _error(exc.code, str(exc))

        decision = request.data.get("decision")
        if decision not in ConsentDecision.values:
            return _error("invalid_input", "Invalid decision.")

        record = token.kii_record
        consent_record = record_consent(
            kii_record=record,
            consent_type=ConsentType.PARTICIPATION,
            decision=decision,
            information_sheet_version=request.data.get("information_sheet_version", ""),
            method=ConsentMethod.WEB_CLICKTHROUGH,
        )
        record.participation_consent = consent_record
        record.save(update_fields=["participation_consent"])

        if decision == ConsentDecision.GIVEN:
            from .services import KIIInvitationTokenStatus, _advance_kii_token_status

            _advance_kii_token_status(token, KIIInvitationTokenStatus.CONSENTED)

        return Response({"id": consent_record.id, "consent_type": consent_record.consent_type, "decision": consent_record.decision})


class KIIKoboRedirectView(APIView):
    """GET /api/v1/kii-invitations/kobo-redirect-url/?t=<token> -- public,
    scoped to the single KIIRecord resolved from the token. Distinguishes
    "not configured" (503, nothing anyone here can fix) from "not consented
    yet" (403, the respondent flow routes this back to the consent step)."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        raw_token = request.query_params.get("t", "")
        try:
            token = validate_kii_token(raw_token)
        except KIITokenValidationError as exc:
            return _error(exc.code, str(exc))

        if not kii_form_is_configured():
            return _error("kobo_not_configured", "The interview form isn't set up yet. Please contact the research team.", status=503)

        record = token.kii_record
        if not has_given_consent(record, ConsentType.PARTICIPATION):
            return _error("consent_required", "Participation consent is required before the interview can open.", status=403)

        from .services import KIIInvitationTokenStatus, _advance_kii_token_status, build_kii_coding_url

        # STARTED, not COMPLETED: this view only hands back the link, it has no way
        # to know whether the informant goes on to actually finish the KoboToolbox
        # form (the KII register's own `status` field is never auto-advanced on
        # submission either -- see apps.kobo.form_sync, which only ever touches
        # coding_status). An RA marks the record COMPLETED, same button as the
        # interviewer-administered path, once the submission is visible on Form PDFs.
        _advance_kii_token_status(token, KIIInvitationTokenStatus.STARTED)
        return Response({"kobo_form_url": build_kii_coding_url(record)})
