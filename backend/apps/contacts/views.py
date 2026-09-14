from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageContact
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.consent.services import has_given_consent
from apps.invitations.models import TokenStatus
from apps.invitations.services import TokenValidationError, advance_token_status, validate_token

from .models import Appointment, AppointmentStatus, ContactEvent, Respondent, RoleCategory
from .serializers import AppointmentSerializer, ContactEventSerializer, StaffRespondentSerializer
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
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

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
        # The API schema generator calls this with no URL kwargs; without the
        # guard it raised KeyError and the endpoint vanished from /api/docs.
        if getattr(self, "swagger_fake_view", False):
            return ContactEvent.objects.none()
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
    # The public POST is the last step of the respondent journey, so it gets
    # the respondent scope rather than falling back to the generic `anon`
    # default. Anon-rate throttles ignore authenticated callers, so the
    # internal GET used by RAs is unaffected.
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

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


def _consent_withdrawn(sample_case) -> bool:
    from apps.consent.models import ConsentDecision, ConsentType
    from apps.consent.services import latest_consent

    record = latest_consent(sample_case, ConsentType.PARTICIPATION)
    return record is not None and record.decision == ConsentDecision.WITHDRAWN


_WITHDRAWN_RESPONSE = {
    "error": {
        "code": "consent_withdrawn",
        "message": "This participant has withdrawn; contact details are not recorded.",
        "field_errors": {},
    }
}


def _save_respondent(serializer, user, **extra):
    """Save a staff edit and audit which fields changed (names, not values --
    the audit log must not become a second copy of the contact register)."""
    from apps.audit.utils import log_action

    instance = serializer.instance
    before = {f: getattr(instance, f) for f in serializer.validated_data} if instance else {}
    if "is_eligible" in serializer.validated_data and serializer.validated_data["is_eligible"] != before.get("is_eligible"):
        extra["eligibility_checked_by"] = user
    respondent = serializer.save(**extra)
    changed = sorted(f for f, v in serializer.validated_data.items() if before.get(f) != v)
    log_action(
        "contacts.respondent_updated" if instance else "contacts.respondent_added",
        respondent,
        {"sample_id": respondent.sample_case.sample_id, "fields": changed, "user_id": user.id},
    )
    return respondent


class RespondentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/contacts/{sample_id}/respondents/ -- the people at a
    case and how to reach them. Until 2026-09-14 there was no way to add or
    correct one: only the register import and the respondent's own
    eligibility answer created them, so 349 of the 400 Main cases had no
    phone number and nowhere to record one."""

    permission_classes = [CanManageContact]
    serializer_class = StaffRespondentSerializer
    pagination_class = None

    def _case(self):
        from apps.sampling.models import SampleCase

        sample_case = get_object_or_404(SampleCase, sample_id=self.kwargs["sample_id"])
        _require_assigned(self.request.user, sample_case)
        return sample_case

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Respondent.objects.none()
        return Respondent.objects.filter(sample_case=self._case()).order_by("id")

    def create(self, request, *args, **kwargs):
        sample_case = self._case()
        if _consent_withdrawn(sample_case):
            return Response(_WITHDRAWN_RESPONSE, status=409)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        respondent = _save_respondent(serializer, request.user, sample_case=sample_case)
        return Response(self.get_serializer(respondent).data, status=201)


class RespondentUpdateView(generics.UpdateAPIView):
    """PATCH /api/v1/contacts/respondents/{id}/"""

    permission_classes = [CanManageContact]
    serializer_class = StaffRespondentSerializer
    http_method_names = ["patch"]
    queryset = Respondent.objects.select_related("sample_case")

    def update(self, request, *args, **kwargs):
        respondent = self.get_object()
        _require_assigned(request.user, respondent.sample_case)
        if _consent_withdrawn(respondent.sample_case):
            return Response(_WITHDRAWN_RESPONSE, status=409)
        serializer = self.get_serializer(respondent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(_save_respondent(serializer, request.user)).data)
