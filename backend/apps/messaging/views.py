from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageContact
from apps.sampling.models import SampleCase

from .models import ReminderSequenceStep
from .services import due_follow_ups, record_manual_follow_up


class FollowUpListView(APIView):
    """GET /api/v1/follow-ups/ -- reminders due and not yet sent, with a
    WhatsApp click-to-chat link carrying the approved reminder text. The
    working queue until the WhatsApp Business Platform sends them itself."""

    permission_classes = [CanManageContact]

    def get(self, request):
        is_contact_ra = getattr(request.user.role, "name", None) == "CONTACT_RA"
        return Response({"results": due_follow_ups(assigned_to=request.user if is_contact_ra else None)})


class FollowUpMarkSentView(APIView):
    """POST /api/v1/follow-ups/mark-sent/ {sample_id, template} -- records a
    reminder sent by hand, against the RA who sent it."""

    permission_classes = [CanManageContact]

    def post(self, request):
        sample_case = get_object_or_404(SampleCase, sample_id=request.data.get("sample_id", ""))
        if getattr(request.user.role, "name", None) == "CONTACT_RA" and sample_case.assigned_ra_id != request.user.id:
            return Response(
                {"error": {"code": "permission_denied", "message": "This case is not assigned to you.", "field_errors": {}}},
                status=403,
            )
        template = request.data.get("template", "")
        if not ReminderSequenceStep.objects.filter(template__name=template).exists():
            return Response(
                {"error": {"code": "invalid_input", "message": "Unknown reminder template.", "field_errors": {}}},
                status=400,
            )
        log = record_manual_follow_up(sample_case=sample_case, template_name=template, user=request.user)
        return Response({"id": log.id, "status": log.status, "sent_at": log.sent_at}, status=201)
