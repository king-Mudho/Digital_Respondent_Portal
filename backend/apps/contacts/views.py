from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from api.permissions import CanManageContact
from api.throttling import PerTokenThrottle
from apps.consent.services import has_given_consent
from apps.invitations.models import TokenStatus
from apps.invitations.services import TokenValidationError, advance_token_status, validate_token

from .models import Appointment, AppointmentStatus, ContactEvent, RoleCategory
from .serializers import AppointmentSerializer, ContactEventSerializer
from .services import record_eligibility_check


def _is_contact_ra(user) -> bool:
    return getattr(getattr(user, "role", None), "name", None) == "CONTACT_RA"


def _require_assigned(user, sample_case):
    """Contact RA's "assigned cases" grant (docs/18) -- raises 403 if this
    Contact RA isn't the case's assigned_ra. A no-op for every other role
    that reaches CanManageContact (Field Coordinator/Admin have no
    assignment restriction; Supervisor never reaches this, it's read-only
    there)."""
    if _is_contact_ra(user) and sample_case.assigned_ra_id != user.id:
        raise PermissionDenied("This case is not assigned to you.")


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
    Coordinator/Admin -- scoped to its assigned cases only."""

    permission_classes = [CanManageContact]
    serializer_class = ContactEventSerializer

    def get_queryset(self):
        queryset = ContactEvent.objects.filter(sample_case__sample_id=self.kwargs["sample_id"])
        if _is_contact_ra(self.request.user):
            queryset = queryset.filter(sample_case__assigned_ra=self.request.user)
        return queryset

    def perform_create(self, serializer):
        from apps.sampling.models import SampleCase

        sample_case = SampleCase.objects.get(sample_id=self.kwargs["sample_id"])
        _require_assigned(self.request.user, sample_case)
        serializer.save(sample_case=sample_case, ra=self.request.user)


class AppointmentListCreateView(generics.ListCreateAPIView):
    """GET /api/v1/appointments/ -- internal register. POST is also reachable
    publicly via a valid token (R09 appointment request,
    docs/10_INVITATION_AND_CONSENT.md participation choices) -- scoped
    strictly to the token-resolved SampleCase, never a list for anonymous
    callers (docs/06_API_ARCHITECTURE.md "Security").

    A public POST requires GIVEN participation consent (PI decision,
    Sep 2026). An appointment request is a researcher-assisted route into
    the same questionnaire, not a separate lightweight enquiry: it records
    a named person's stated availability against an identified
    organisation and puts them on an RA's call list. Reaching that without
    having agreed to take part would collect contact data outside consent,
    so the same gate applies here as on the self-administered route."""

    serializer_class = AppointmentSerializer
    filterset_fields = ["status", "mode"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [CanManageContact()]

    def get_queryset(self):
        # sample_case__organisation is joined for the serializer's
        # organisation_name, which would otherwise be a query per row.
        queryset = Appointment.objects.select_related(
            "sample_case__organisation", "kii_record"
        ).order_by("scheduled_for")
        if _is_contact_ra(self.request.user):
            queryset = queryset.filter(sample_case__assigned_ra=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        raw_token = request.data.get("token", "")
        try:
            token = validate_token(raw_token)
        except TokenValidationError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)

        if not has_given_consent(token.sample_case):
            return Response(
                {"error": {
                    "code": "consent_required",
                    "message": "Participation consent has not been given.",
                    "field_errors": {},
                }},
                status=403,
            )

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
        if appointment.sample_case_id and _is_contact_ra(request.user):
            _require_assigned(request.user, appointment.sample_case)
        status_value = request.data.get("status")
        if status_value not in AppointmentStatus.values:
            return Response(
                {"error": {"code": "invalid_status", "message": "Invalid status.", "field_errors": {}}}, status=400
            )
        appointment.status = status_value
        appointment.save(update_fields=["status"])
        return Response(AppointmentSerializer(appointment).data)
