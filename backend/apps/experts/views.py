from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageExperts
from api.throttling import PerTokenThrottle, RespondentRateThrottle

from . import instrument
from .models import ExpertInvitationToken, ExpertRecord, ExpertStatus, PanelArea
from .services import (
    ExpertError,
    completed_count,
    create_expert,
    form_is_configured,
    invitations_open,
    issue_invitation,
    open_questionnaire,
    panel,
    record_expert_consent,
    revoke,
    validate_code,
    validate_token,
)

EDITABLE = ("full_name", "title", "institution", "institution_category", "panel_area", "years_experience", "phone",
            "whatsapp_number", "email", "conflicts_note", "notes")
# What staff may set by hand: a decline taken by phone, or back to not-yet-invited. Consent and completion come only
# from the expert's own consent and the KoboToolbox submission.
MANUAL_STATUSES = (ExpertStatus.PROSPECT, ExpertStatus.DECLINED)


def _error(exc: ExpertError):
    return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)


def _row(e: ExpertRecord) -> dict:
    token = e.invitation_tokens.first()
    return {
        "expert_id": e.expert_id, "full_name": e.full_name, "title": e.title, "institution": e.institution,
        "institution_category": e.institution_category, "panel_area": e.panel_area, "panel_area_label": e.get_panel_area_display(),
        "years_experience": e.years_experience, "phone": e.phone, "whatsapp_number": e.whatsapp_number, "email": e.email,
        "conflicts_note": e.conflicts_note, "notes": e.notes, "status": e.status, "status_label": e.get_status_display(),
        "completed_at": e.completed_at, "created_at": e.created_at,
        "link": {"status": token.get_status_display(), "issued_at": token.issued_at, "expires_at": token.expires_at,
                 "channel": token.channel} if token else None,
    }


def _clean(data, *, partial: bool) -> dict:
    fields = {k: data[k] for k in EDITABLE if k in data}
    for key in ("full_name",):
        if key in fields and not str(fields[key]).strip():
            raise ExpertError("invalid_input", "Write the expert's name.")
    if not partial and not str(data.get("full_name", "")).strip():
        raise ExpertError("invalid_input", "Write the expert's name.")
    if "panel_area" in fields or not partial:
        if fields.get("panel_area") not in PanelArea.values:
            raise ExpertError("invalid_input", "Choose the expert's panel area.")
    if "years_experience" in fields:
        value = str(fields["years_experience"] or "").strip()
        if value and not value.isdigit():
            raise ExpertError("invalid_input", "Years of experience must be a number.")
        fields["years_experience"] = int(value) if value else None
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items()}


class ExpertListView(APIView):
    """GET /api/v1/experts/ -- the panel: every expert, the panel areas against their targets, how many have completed
    of EXPERT_TARGET, and whether invitations can go out. POST -- register an expert (PI, Field Coordinator)."""

    permission_classes = [CanManageExperts]

    def get(self, request):
        experts = ExpertRecord.objects.prefetch_related("invitation_tokens")
        return Response({
            "results": [_row(e) for e in experts], "panel": panel(), "completed": completed_count(),
            "target": settings.EXPERT_TARGET, "invitations_closed": invitations_open(), "form_configured": form_is_configured(),
            "panel_areas": [{"value": a.value, "label": a.label} for a in PanelArea],
            "institution_categories": [{"value": v, "label": label} for v, label in instrument.INSTITUTION],
        })

    def post(self, request):
        try:
            expert = create_expert(user=request.user, **_clean(request.data, partial=False))
        except ExpertError as exc:
            return _error(exc)
        return Response(_row(expert), status=201)


class ExpertDetailView(APIView):
    """GET/PATCH /api/v1/experts/<expert_id>/ -- one expert with their invitation history; PATCH edits their details,
    or records a decline taken by phone (status DECLINED) or puts them back to PROSPECT."""

    permission_classes = [CanManageExperts]

    def get(self, request, expert_id):
        expert = get_object_or_404(ExpertRecord, expert_id=expert_id)
        return Response({**_row(expert), "invitations": [
            {"id": t.id, "status": t.status, "status_label": t.get_status_display(), "channel": t.channel,
             "issued_at": t.issued_at, "expires_at": t.expires_at, "first_opened_at": t.first_opened_at,
             "revoked_reason": t.revoked_reason} for t in expert.invitation_tokens.all()],
            "consent": {"decision": expert.participation_consent.decision, "at": expert.participation_consent.timestamp}
            if expert.participation_consent_id else None})

    def patch(self, request, expert_id):
        from apps.audit.utils import log_action

        expert = get_object_or_404(ExpertRecord, expert_id=expert_id)
        try:
            fields = _clean(request.data, partial=True)
            status = request.data.get("status")
            if status is not None:
                if status not in MANUAL_STATUSES:
                    raise ExpertError("invalid_status", "Only a decline, or back to not yet invited, is set by hand.")
                if expert.status == ExpertStatus.COMPLETED:
                    raise ExpertError("invalid_status", "This expert has completed the questionnaire.")
                fields["status"] = status
        except ExpertError as exc:
            return _error(exc)
        for key, value in fields.items():
            setattr(expert, key, value)
        expert.save()
        log_action("expert.updated", expert, {"expert_id": expert.expert_id, "fields": sorted(fields)}, user=request.user)
        return Response(_row(expert))


class ExpertInvitationIssueView(APIView):
    """POST /api/v1/expert-invitations/ {expert_id, channel} -- a new personal link (replacing an open one), with the
    message for each channel. Refused until the ethics reference is recorded, and once the panel is complete."""

    permission_classes = [CanManageExperts]

    def post(self, request):
        from apps.invitations.messages import portal_base
        from apps.kobo.submission_copies import email_is_configured

        from .messages import build_messages, recipients

        expert = get_object_or_404(ExpertRecord, expert_id=request.data.get("expert_id", ""))
        try:
            raw, code, token = issue_invitation(expert, channel=request.data.get("channel", "WHATSAPP"), issued_by=request.user)
        except ExpertError as exc:
            return _error(exc)
        link = f"{portal_base(request.data.get('link_base'))}/ex/{raw}"
        return Response({
            "token_id": token.id, "raw_token": raw, "raw_manual_code": code, "expires_at": token.expires_at, "link": link,
            **recipients(expert), "email_configured": email_is_configured(), "sms_configured": False,
            "whatsapp_configured": False,
            "messages": build_messages(expert=expert, link=link, manual_code=code, expires_at=token.expires_at),
        }, status=201)


class ExpertInvitationEmailView(APIView):
    """POST /api/v1/expert-invitations/<token_id>/send-email/ {link, manual_code}."""

    permission_classes = [CanManageExperts]

    def post(self, request, token_id):
        from .messages import email_invitation

        token = get_object_or_404(ExpertInvitationToken.objects.select_related("expert"), pk=token_id)
        try:
            return Response(email_invitation(token, link=str(request.data.get("link", "")),
                                             manual_code=str(request.data.get("manual_code", "")), user=request.user))
        except ExpertError as exc:
            return _error(exc)
        except Exception as exc:  # the mail server refused or timed out
            return _error(ExpertError("email_failed", f"The email could not be sent ({exc.__class__.__name__}).", 502))


class ExpertInvitationRevokeView(APIView):
    """POST /api/v1/expert-invitations/<token_id>/revoke/ {reason}."""

    permission_classes = [CanManageExperts]

    def post(self, request, token_id):
        token = get_object_or_404(ExpertInvitationToken.objects.select_related("expert"), pk=token_id)
        revoke(token, str(request.data.get("reason", "")), user=request.user)
        return Response({"status": "revoked"})


# --- The expert's own link (public: the token is the only credential) ----------------------------------------------

def _resolve(request):
    raw_token, raw_code = request.query_params.get("t") or request.data.get("token"), request.query_params.get("code")
    if raw_token:
        return validate_token(raw_token)
    if raw_code:
        return validate_code(raw_code)
    raise ExpertError("token_missing", "A link or code is required.")


class ExpertValidateView(APIView):
    """GET /api/v1/expert-invitations/validate/?t=<token> (or ?code=) -- the expert's own name (the invitation was
    addressed to them) and the information they read before consenting."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        try:
            token = _resolve(request)
        except ExpertError as exc:
            return _error(exc)
        return Response({
            "status": "valid", "expert_name": token.expert.full_name, "expert_id": token.expert.expert_id,
            "consented": token.expert.status in (ExpertStatus.CONSENTED, ExpertStatus.COMPLETED),
            "completed": token.expert.status == ExpertStatus.COMPLETED,
            "information": [{"title": t, "text": text} for t, text in instrument.INFORMATION],
            "ethics_line": instrument.ETHICS_LINE, "consent_statements": [t for _, t in instrument.CONSENT_STATEMENTS],
            "information_sheet_version": instrument.INFORMATION_SHEET_VERSION,
        })


class ExpertConsentView(APIView):
    """POST /api/v1/expert-consent/ {token, decision, information_sheet_version} -- public, for the one expert the
    token names."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def post(self, request):
        try:
            token = validate_token(str(request.data.get("token", "")))
            consent = record_expert_consent(token, decision=str(request.data.get("decision", "")),
                                            information_sheet_version=str(request.data.get("information_sheet_version", "")))
        except ExpertError as exc:
            return _error(exc)
        return Response({"id": consent.id, "decision": consent.decision})


class ExpertKoboRedirectView(APIView):
    """GET /api/v1/expert-invitations/kobo-redirect-url/?t=<token> -- the questionnaire with the Expert ID filled in.
    403 until the expert has consented; 503 while the form isn't connected."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        try:
            return Response({"kobo_form_url": open_questionnaire(validate_token(request.query_params.get("t", "")))})
        except ExpertError as exc:
            return _error(exc)
