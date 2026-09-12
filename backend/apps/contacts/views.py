from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from api.permissions import CanManageContact
from api.throttling import PerTokenThrottle
from apps.invitations.models import TokenStatus
from apps.invitations.services import TokenValidationError, advance_token_status, validate_token

from .models import Appointment, AppointmentStatus, ContactEvent, RoleCategory
from .serializers import AppointmentSerializer, ContactEventSerializer
from .services import record_eligibility_check


class EligibilityView(APIView):
    """POST /api/v1/eligibility/ -- public. Determines whether the
    respondent is a knowledgeable organisational respondent from the fixed
    role-category list (docs/10_INVITATION_AND_CONSENT.md) -- not a bare
    self-certified checkbox: eligibility follows from actually selecting a
    real role from that list, not from a separate yes/no the client could
    set arbitrarily. If ineligible, the questionnaire never opens
    (Respondent.is_eligible stays False; the referral path is a frontend
    concern, not a backend endpoint)."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, AnonRateThrottle]

    def post(self, request):
        raw_token = request.data.get("token", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        full_name = request.data.get("full_name", "")
        role_category = request.data.get("role_category", "")
        is_eligible = role_category in RoleCategory.values

        respondent = record_eligibility_check(
            sample_case=token.sample_case,
            full_name=full_name,
            role_category=role_category if is_eligible else "",
            is_eligible=is_eligible,
        )

        if is_eligible:
            advance_token_status(token, TokenStatus.ELIGIBILITY_PASSED)

        return Response({"respondent_id": respondent.id, "is_eligible": respondent.is_eligible})


class ContactEventListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/contacts/{sample_id}/events/ -- internal only.
    CanManageContact: this is the Contact RA's actual job, not just Field
    Coordinator/Admin."""

    permission_classes = [CanManageContact]
    serializer_class = ContactEventSerializer

    def get_queryset(self):
        return ContactEvent.objects.filter(sample_case__sample_id=self.kwargs["sample_id"])

    def perform_create(self, serializer):
        from apps.sampling.models import SampleCase

        sample_case = SampleCase.objects.get(sample_id=self.kwargs["sample_id"])
        serializer.save(sample_case=sample_case, ra=self.request.user)


class AppointmentListCreateView(generics.ListCreateAPIView):
    """GET /api/v1/appointments/ -- internal register. POST is also reachable
    publicly via a valid token (R09 appointment request,
    docs/10_INVITATION_AND_CONSENT.md participation choices) -- scoped
    strictly to the token-resolved SampleCase, never a list for anonymous
    callers (docs/06_API_ARCHITECTURE.md "Security")."""

    serializer_class = AppointmentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [CanManageContact()]

    def get_queryset(self):
        return Appointment.objects.select_related("sample_case", "kii_record").order_by("scheduled_for")

    def create(self, request, *args, **kwargs):
        raw_token = request.data.get("token", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        serializer = self.get_serializer(data={
            "sample_case": token.sample_case.id,
            "scheduled_for": request.data.get("scheduled_for"),
            "mode": request.data.get("mode"),
        })
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class AppointmentStatusView(APIView):
    """POST /api/v1/appointments/{id}/status/ -- internal only. Appointment.
    status is deliberately read-only on AppointmentSerializer (a public
    caller creating an appointment must never set its own status), so
    updating it needs this dedicated endpoint, same pattern as KII's status
    transition view."""

    permission_classes = [CanManageContact]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        status_value = request.data.get("status")
        if status_value not in AppointmentStatus.values:
            return Response(
                {"error": {"code": "invalid_status", "message": "Invalid status.", "field_errors": {}}}, status=400
            )
        appointment.status = status_value
        appointment.save(update_fields=["status"])
        return Response(AppointmentSerializer(appointment).data)
