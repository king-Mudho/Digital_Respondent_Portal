from datetime import timedelta

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanRunInterviewVerification, IsFieldCoordinatorOrAdmin
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.audit.utils import log_action
from apps.invitations.services import TokenValidationError, validate_token

from .ai_research import AIResearchError, ai_research_is_configured, case_context
from .models import (
    PROIT_FIELD_CATALOG,
    AIProposal,
    AIResearchRun,
    AIResearchStatus,
    EvidenceSource,
    PreProfile,
    PreProfileField,
)
from .serializers import (
    AIProposalSerializer,
    AIResearchRunSerializer,
    EvidenceSourceSerializer,
    PreProfileFieldSerializer,
    PreProfileSerializer,
    RespondentPreProfileFieldSerializer,
)
from .services import (
    PROBE_TEMPLATES,
    PreProfileError,
    PreProfileLocked,
    PreProfileNotLocked,
    accept_proposal,
    add_evidence,
    add_field,
    compute_burden_metrics,
    field_is_displayable,
    field_is_settled,
    lock_pre_profile,
    reconcile_field,
    reconciliation_state,
    record_protocol_deviation,
    record_verification,
    refresh_reconciliation,
    reject_proposal,
)
from .tasks import research_pre_profile


class FieldCatalogView(APIView):
    """GET /api/v1/proit/field-catalog/ -- the whitelist of pre-fillable
    field IDs (document Section 6, modules A-F), for the admin UI's "add
    field" picker."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        return Response({
            field_id: {"label": label, "module": module, "route": route}
            for field_id, (label, module, route) in PROIT_FIELD_CATALOG.items()
        })


class ProbeTemplateView(APIView):
    """GET /api/v1/proit/probe-templates/ -- the KII probe-template
    library (document Section 10), for the KII gap-engine panel to offer
    as one-click suggestions."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        return Response({
            role: {"trigger": trigger, "template": template}
            for role, (trigger, template) in PROBE_TEMPLATES.items()
        })


class PreProfileListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/proit/pre-profiles/?sample_case=<id> or
    ?kii_record=<id>."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = PreProfileSerializer

    def get_queryset(self):
        qs = PreProfile.objects.select_related("sample_case", "kii_record").prefetch_related("fields__sources")
        sample_case = self.request.query_params.get("sample_case")
        kii_record = self.request.query_params.get("kii_record")
        if sample_case:
            qs = qs.filter(sample_case_id=sample_case)
        if kii_record:
            qs = qs.filter(kii_record_id=kii_record)
        return qs


class PreProfileDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/proit/pre-profiles/{id}/ -- PATCH is for the
    Module H/I/J workflow fields a researcher fills in directly
    (known_evidence_summary, unresolved_gaps, deviation_note, etc.); the
    lock itself is a dedicated action (PreProfileLockView), not a plain
    field write, since it has side effects (gap classification, immutability)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = PreProfileSerializer
    queryset = PreProfile.objects.select_related("sample_case", "kii_record").prefetch_related("fields__sources")


class PreProfileLockView(APIView):
    """POST /api/v1/proit/pre-profiles/{id}/lock/."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        pre_profile = get_object_or_404(PreProfile, pk=pk)
        try:
            lock_pre_profile(pre_profile, reviewer=request.user)
        except PreProfileError as exc:
            return Response({"error": {"code": "lock_failed", "message": str(exc), "field_errors": {}}}, status=400)
        compute_burden_metrics(pre_profile)
        pre_profile.refresh_from_db()
        return Response(PreProfileSerializer(pre_profile).data)


class PreProfileFieldListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/proit/pre-profiles/{pre_profile_id}/fields/."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = PreProfileFieldSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation passes no kwargs
            return PreProfileField.objects.none()
        return PreProfileField.objects.filter(pre_profile_id=self.kwargs["pre_profile_id"]).prefetch_related("sources")

    def create(self, request, *args, **kwargs):
        pre_profile = get_object_or_404(PreProfile, pk=self.kwargs["pre_profile_id"])
        field_id = request.data.get("field_id")
        documentary_value = request.data.get("preliminary_documentary_value", "")
        if field_id not in PROIT_FIELD_CATALOG:
            return Response(
                {"error": {"code": "invalid_field_id", "message": f"{field_id!r} is not a valid PROIT field.", "field_errors": {}}},
                status=400,
            )
        try:
            field = add_field(pre_profile, field_id, documentary_value=documentary_value)
        except PreProfileError as exc:
            return Response({"error": {"code": "add_field_failed", "message": str(exc), "field_errors": {}}}, status=400)
        return Response(PreProfileFieldSerializer(field).data, status=201)


class EvidenceSourceListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/proit/fields/{field_id}/evidence/."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = EvidenceSourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation passes no kwargs
            return EvidenceSource.objects.none()
        return EvidenceSource.objects.filter(field_id=self.kwargs["field_id"])

    def create(self, request, *args, **kwargs):
        field = get_object_or_404(PreProfileField, pk=self.kwargs["field_id"])
        data = dict(request.data)
        source_title = data.pop("source_title", None)
        source_confidence = data.pop("source_confidence", None)
        if not source_title or not source_confidence:
            return Response(
                {"error": {"code": "invalid_input", "message": "source_title and source_confidence are required.", "field_errors": {}}},
                status=400,
            )
        try:
            source = add_evidence(
                field, source_title=source_title, source_confidence=source_confidence,
                created_by=request.user, **data,
            )
        except PreProfileError as exc:
            return Response({"error": {"code": "add_evidence_failed", "message": str(exc), "field_errors": {}}}, status=400)
        field.refresh_from_db()
        return Response(EvidenceSourceSerializer(source).data, status=201)


# --- Respondent-facing (token-based, public) --------------------------------

class RespondentPreProfileView(APIView):
    """GET /api/v1/proit/respondent-profile/?t=<token> -- public. Returns
    null when PROIT is disabled for respondents (settings.
    PROIT_ENABLED_FOR_RESPONDENTS, the ethics/change-control gate), when no
    pre-profile exists for this case, or when it isn't locked yet -- the
    respondent flow treats all three identically (skip straight to the
    next step) rather than distinguishing "not built" from "not approved"."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        if not settings.PROIT_ENABLED_FOR_RESPONDENTS:
            return Response(None)

        raw_token = request.query_params.get("t", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        pre_profile = PreProfile.objects.filter(
            sample_case=token.sample_case, prepopulation_locked_at__isnull=False,
        ).first()
        if pre_profile is None:
            return Response(None)

        displayable = [f for f in pre_profile.fields.all() if field_is_displayable(f)]
        return Response({
            "pre_profile_id": pre_profile.id,
            "fields": RespondentPreProfileFieldSerializer(displayable, many=True).data,
        })


class RespondentVerifyView(APIView):
    """POST /api/v1/proit/respondent-verify/ -- public, one field per
    call. Scoped to the token's own case: a respondent can only verify a
    field belonging to the pre-profile resolved from their own token."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def post(self, request):
        if not settings.PROIT_ENABLED_FOR_RESPONDENTS:
            return Response({"error": {"code": "proit_disabled", "message": "Not available.", "field_errors": {}}}, status=403)

        raw_token = request.data.get("token", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        field = get_object_or_404(
            PreProfileField, pk=request.data.get("field_id"), pre_profile__sample_case=token.sample_case,
        )
        status_code = request.data.get("status")
        try:
            record_verification(
                field, status=status_code,
                respondent_value=request.data.get("respondent_value", ""),
                comment=request.data.get("comment", ""),
            )
        except PreProfileError as exc:
            return Response({"error": {"code": "verification_failed", "message": str(exc), "field_errors": {}}}, status=400)
        return Response({"id": field.id, "verification_status": field.verification_status})


# --- AI desk research: the AI proposes, a researcher decides ------------------------------------------

class AIResearchView(APIView):
    """POST /api/v1/proit/pre-profiles/{id}/ai-research/ -- start an AI desk-research pass in the
    background (202). GET -- the latest run and every proposal so far. PROIT is the Field Coordinator's
    and PI's tool; Supervisor may read."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request, pk):
        profile = get_object_or_404(PreProfile, pk=pk)
        run = profile.ai_runs.first()
        proposals = AIProposal.objects.filter(pre_profile=profile).order_by("id")
        return Response({
            "configured": ai_research_is_configured(),
            "run": AIResearchRunSerializer(run).data if run else None,
            "proposals": AIProposalSerializer(proposals, many=True).data,
        })

    def post(self, request, pk):
        profile = get_object_or_404(PreProfile, pk=pk)
        if not ai_research_is_configured():
            return _error("ai_not_configured", "AI research hasn't been set up (ANTHROPIC_API_KEY).", 503)
        if profile.prepopulation_locked_at is not None:
            return _error("locked", "This pre-profile is locked, so it cannot be researched again.", 409)
        running = profile.ai_runs.filter(status=AIResearchStatus.RUNNING).first()
        if running and timezone.now() - running.started_at < timedelta(minutes=15):
            return _error("already_running", "AI research is already running for this profile.", 409)
        try:
            case_context(profile)  # refuse now, not minutes later, if there is no organisation to research
        except AIResearchError as exc:
            return _error(exc.code, str(exc), exc.status)
        if running:  # a run that never finished (worker restarted): close it so it stops blocking
            running.status, running.error, running.finished_at = AIResearchStatus.FAILED, "Interrupted.", timezone.now()
            running.save(update_fields=["status", "error", "finished_at"])
        run = AIResearchRun.objects.create(pre_profile=profile, requested_by=request.user, model=settings.AI_DOCUMENT_CODING_MODEL)
        log_action("proit.ai_research_started", profile, {"run": run.pk, "user_id": request.user.id})
        research_pre_profile.delay(run.pk)
        run.refresh_from_db()
        return Response(AIResearchRunSerializer(run).data, status=202)


class AIProposalAcceptView(APIView):
    """POST /api/v1/proit/ai-proposals/{id}/accept/ {value?} -- the researcher accepts a finding, optionally
    correcting its wording first. Only now does it become a background field with its sources."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        proposal = get_object_or_404(AIProposal, pk=pk)
        value = request.data.get("value")
        try:
            accept_proposal(proposal, user=request.user, value=value if isinstance(value, str) else None)
        except PreProfileError as exc:
            return _error("accept_failed", str(exc), 409 if isinstance(exc, PreProfileLocked) else 400)
        proposal.refresh_from_db()
        return Response(AIProposalSerializer(proposal).data)


class AIProposalRejectView(APIView):
    """POST /api/v1/proit/ai-proposals/{id}/reject/ {reason?}"""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        proposal = get_object_or_404(AIProposal, pk=pk)
        try:
            reject_proposal(proposal, user=request.user, reason=str(request.data.get("reason") or "").strip()[:300])
        except PreProfileError as exc:
            return _error("reject_failed", str(exc), 400)
        return Response(AIProposalSerializer(proposal).data)


# --- Verification before, reconciliation after -----------------------------------------------------

def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


def _scoped_profile_or_404(request, profile):
    """A Contact RA only reaches the pre-profile of a case assigned to them (404, so its existence is not leaked)."""
    role = getattr(request.user.role, "name", None)
    if role == "CONTACT_RA":
        if profile.sample_case_id is None or profile.sample_case.assigned_ra_id != request.user.id:
            raise Http404
    if role == "KII_RA" and profile.kii_record_id is None:
        raise Http404
    return profile


class InterviewSheetView(APIView):
    """GET /api/v1/proit/interview-sheet/?sample_case=<id>|?kii_record=<id> -- the locked pre-profile as the
    interviewer uses it: each fact to CONFIRM (with its public source), each gap to ASK, and where the
    respondent's answers stand. Only a locked profile is shown. A LOW-confidence value is withheld (it is a
    question to ask, never a fact to state)."""

    permission_classes = [CanRunInterviewVerification]

    def get(self, request):
        qs = PreProfile.objects.select_related("sample_case", "kii_record").prefetch_related("fields__sources")
        if request.query_params.get("sample_case"):
            qs = qs.filter(sample_case_id=request.query_params["sample_case"])
        elif request.query_params.get("kii_record"):
            qs = qs.filter(kii_record_id=request.query_params["kii_record"])
        else:
            return _error("invalid_input", "sample_case or kii_record is required.", 400)
        profile = qs.first()
        if profile is None:
            return Response({"profile": None})
        _scoped_profile_or_404(request, profile)
        if profile.prepopulation_locked_at is None:
            return Response({"profile": None, "locked": False})
        refresh_reconciliation(profile)
        fields = []
        for f in profile.fields.all():
            shown = f.preliminary_documentary_value if field_is_displayable(f) else ""
            fields.append({
                "id": f.id, "field_id": f.field_id, "label": f.label, "module": f.module,
                "documentary_value": shown, "withheld_low_confidence": bool(f.preliminary_documentary_value) and not shown,
                "confidence": f.confidence, "gap_classification": f.gap_classification,
                "sources": [{"title": s.source_title, "publisher": s.publisher, "url": s.locator,
                             "date": s.source_date.isoformat() if s.source_date else ""} for s in f.sources.all()],
                "verification_status": f.verification_status, "respondent_value": f.respondent_value,
                "verification_comment": f.verification_comment, "reconciled_value": f.reconciled_value,
                "settled": field_is_settled(f),
            })
        return Response({
            "locked": True,
            "profile": {
                "id": profile.id, "sample_id": profile.sample_case.sample_id if profile.sample_case_id else None,
                "kii_id": profile.kii_record.kii_id if profile.kii_record_id else None,
                "priority_probe_questions": profile.priority_probe_questions, "unresolved_gaps": profile.unresolved_gaps,
                "contradictions": profile.contradictions, "fields": fields,
                "reconciliation": reconciliation_state(profile), "deviation_note": profile.deviation_note,
                "kobo_submitted_at": profile.kobo_submitted_at,
            },
        })


class FieldVerifyView(APIView):
    """POST /api/v1/proit/fields/{id}/verify/ {status, respondent_value?, comment?} -- the interviewer records
    what the respondent said about one fact: confirmed, corrected, qualified, not known, declined, not applicable.
    Never touches the documentary value."""

    permission_classes = [CanRunInterviewVerification]

    def post(self, request, pk):
        field = get_object_or_404(PreProfileField.objects.select_related("pre_profile"), pk=pk)
        _scoped_profile_or_404(request, field.pre_profile)
        try:
            record_verification(
                field, status=request.data.get("status", ""), respondent_value=str(request.data.get("respondent_value") or ""),
                comment=str(request.data.get("comment") or ""),
            )
        except PreProfileError as exc:
            return _error("verification_failed", str(exc), 409 if isinstance(exc, PreProfileNotLocked) else 400)
        refresh_reconciliation(field.pre_profile)
        log_action("proit.field_verified", field.pre_profile, {"field_id": field.field_id, "status": field.verification_status, "user_id": request.user.id})
        return Response({"id": field.id, "verification_status": field.verification_status, "settled": field_is_settled(field)})


class FieldReconcileView(APIView):
    """POST /api/v1/proit/fields/{id}/reconcile/ {reconciled_value} -- the researcher's coded position after the
    interview, where the respondent corrected, qualified, did not know or declined. Coordinator/PI only."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        field = get_object_or_404(PreProfileField.objects.select_related("pre_profile"), pk=pk)
        if not field.verification_status:
            return _error("not_verified", "Verify this fact with the respondent before reconciling it.", 409)
        value = str(request.data.get("reconciled_value") or "").strip()
        if not value:
            return _error("invalid_input", "Enter the reconciled value.", 400)
        reconcile_field(field, reconciled_value=value)
        refresh_reconciliation(field.pre_profile)
        log_action("proit.field_reconciled", field.pre_profile, {"field_id": field.field_id, "user_id": request.user.id})
        return Response({"id": field.id, "reconciled_value": field.reconciled_value, "settled": field_is_settled(field)})


class InterviewCompleteView(APIView):
    """POST /api/v1/proit/pre-profiles/{id}/interview-complete/ -- the interviewer records that the interview
    (and the verification during it) is finished, so reconciliation can begin."""

    permission_classes = [CanRunInterviewVerification]

    def post(self, request, pk):
        profile = get_object_or_404(PreProfile.objects.select_related("sample_case", "kii_record"), pk=pk)
        _scoped_profile_or_404(request, profile)
        if profile.prepopulation_locked_at is None:
            return _error("not_locked", "This pre-profile was never locked, so there is nothing to reconcile.", 409)
        if profile.interview_completed_at is None:
            profile.interview_completed_at = timezone.now()
            profile.save(update_fields=["interview_completed_at"])
            log_action("proit.interview_completed", profile, {"user_id": request.user.id})
        refresh_reconciliation(profile)
        return Response(reconciliation_state(profile))


class ProtocolDeviationView(APIView):
    """POST /api/v1/proit/pre-profiles/{id}/deviation/ {note} -- when reconciliation truly cannot be finished, the
    coordinator releases the case by recording why; it stays flagged. Coordinator/PI only."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        profile = get_object_or_404(PreProfile, pk=pk)
        try:
            record_protocol_deviation(profile, note=str(request.data.get("note") or ""), user=request.user)
        except PreProfileError as exc:
            return _error("deviation_failed", str(exc), 400)
        return Response(reconciliation_state(profile))
