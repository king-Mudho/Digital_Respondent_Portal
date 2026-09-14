from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.invitations.services import TokenValidationError, validate_token

from .models import PROIT_FIELD_CATALOG, EvidenceSource, PreProfile, PreProfileField
from .serializers import (
    EvidenceSourceSerializer,
    PreProfileFieldSerializer,
    PreProfileSerializer,
    RespondentPreProfileFieldSerializer,
)
from .services import (
    PROBE_TEMPLATES,
    PreProfileError,
    add_evidence,
    add_field,
    compute_burden_metrics,
    field_is_displayable,
    lock_pre_profile,
    record_verification,
)


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
