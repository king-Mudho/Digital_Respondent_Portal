from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageContact
from apps.sampling.models import SampleCase

from .models import ReminderSequenceStep
from .services import due_follow_ups, expired_invitations, record_manual_follow_up


class FollowUpListView(APIView):
    """GET /api/v1/follow-ups/ -- reminders due and not yet sent, with a
    WhatsApp click-to-chat link carrying the approved reminder text. The
    working queue until the WhatsApp Business Platform sends them itself."""

    permission_classes = [CanManageContact]

    def get(self, request):
        from .outreach import unanswered

        is_contact_ra = getattr(request.user.role, "name", None) == "CONTACT_RA"
        mine = request.user if is_contact_ra else None
        return Response({"results": due_follow_ups(assigned_to=mine), "expired": expired_invitations(assigned_to=mine),
                         "unanswered_introductions": unanswered(assigned_to=mine)})


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


class TwilioStatusView(APIView):
    """POST /api/v1/twilio/status/ -- Twilio's delivery reports for the messages the portal sent (2026-10-07).

    Public, like the Kobo webhook, so the only credential is Twilio's X-Twilio-Signature over the callback URL and
    the posted fields, keyed with the account's Auth Token. Anything without a valid signature is refused before it
    touches a record."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser]

    def post(self, request):
        from . import outbound, twilio_client

        params = {key: request.POST.get(key) for key in request.POST}
        signature = request.headers.get("X-Twilio-Signature", "")
        if not twilio_client.valid_signature(twilio_client.status_callback_url(), params, signature):
            return Response({"error": {"code": "invalid_signature", "message": "Invalid signature.", "field_errors": {}}}, status=403)
        outbound.record_status(params)
        return Response(status=204)


class TwilioInboundView(APIView):
    """POST /api/v1/twilio/inbound/ -- messages people send to the study's WhatsApp number (2026-10-07), set as the
    WhatsApp sender's incoming-message webhook in the Twilio console. Refused without a valid X-Twilio-Signature. The
    message is stored and acted on in the background (outreach.handle_inbound), so Twilio gets its answer at once."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser]

    def post(self, request):
        from django.http import HttpResponse

        from . import outreach, twilio_client
        from .tasks import handle_inbound_message

        params = {key: request.POST.get(key) for key in request.POST}
        if not twilio_client.valid_signature(twilio_client.inbound_url(), params, request.headers.get("X-Twilio-Signature", "")):
            return Response({"error": {"code": "invalid_signature", "message": "Invalid signature.", "field_errors": {}}}, status=403)
        message, digits = outreach.record_inbound(params)
        if message is not None:
            handle_inbound_message.delay(message.pk, digits)
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type="text/xml")


def _conversation_row(message, user) -> dict:
    from .outreach import reply_window_open

    case = message.sample_case
    return {
        "id": message.id, "received_at": message.received_at, "from": message.from_masked, "body": message.body,
        "kind": message.kind, "auto_reply": message.auto_reply, "needs_person": message.needs_person,
        "handled_by": message.handled_by.username if message.handled_by else "", "handled_at": message.handled_at,
        "sample_id": case.sample_id if case else "", "organisation_name": case.organisation.name if case else "",
        "outreach_status": message.outreach.get_status_display() if message.outreach else "",
        "can_reply": reply_window_open(message.number_hash),
    }


def _visible_messages(user):
    from .models import InboundMessage

    messages = InboundMessage.objects.select_related("sample_case__organisation", "outreach", "handled_by")
    if getattr(user.role, "name", None) == "CONTACT_RA":
        # A Contact RA sees their own cases' conversations; messages from unknown numbers go to the PI and FC.
        messages = messages.filter(sample_case__assigned_ra=user)
    return messages


class ConversationListView(APIView):
    """GET /api/v1/conversations/?show=open|all -- WhatsApp messages received (2026-10-07). Open first: those waiting
    for a person. CanManageContact: Supervisor reads, a Contact RA sees only their own cases."""

    permission_classes = [CanManageContact]

    def get(self, request):
        messages = _visible_messages(request.user)
        if request.query_params.get("show", "open") == "open":
            messages = messages.filter(needs_person=True, handled_at__isnull=True)
        return Response({"results": [_conversation_row(m, request.user) for m in messages.order_by("-received_at")[:200]]})


class ConversationHandledView(APIView):
    """POST /api/v1/conversations/{id}/handled/ -- a person has dealt with it."""

    permission_classes = [CanManageContact]

    def post(self, request, pk):
        from django.utils import timezone

        message = get_object_or_404(_visible_messages(request.user), pk=pk)
        message.handled_by, message.handled_at, message.needs_person = request.user, timezone.now(), False
        message.save(update_fields=["handled_by", "handled_at", "needs_person"])
        return Response(_conversation_row(message, request.user))


class ConversationReplyView(APIView):
    """POST /api/v1/conversations/{id}/reply/ {text} -- answer in the WhatsApp chat, within WhatsApp's 24 hours."""

    permission_classes = [CanManageContact]

    def post(self, request, pk):
        from .outreach import OutreachError, reply_from_inbox

        message = get_object_or_404(_visible_messages(request.user), pk=pk)
        try:
            reply_from_inbox(message, str(request.data.get("text", "")), user=request.user)
        except OutreachError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        message.refresh_from_db()
        return Response(_conversation_row(message, request.user))


class CaseOutreachView(APIView):
    """GET /api/v1/outreach/?sample_id= -- a case's introductions and the replies received.
    POST /api/v1/outreach/ {sample_id} -- send the "ask first" introduction (2026-10-07). A Contact RA only for their
    own cases, as for invitations."""

    permission_classes = [CanManageContact]

    def get(self, request):
        from .models import Outreach
        from .outreach import intro_channel

        case = get_object_or_404(SampleCase, sample_id=request.query_params.get("sample_id"))
        if getattr(request.user.role, "name", None) == "CONTACT_RA" and case.assigned_ra_id != request.user.id:
            return Response({"error": {"code": "forbidden", "message": "This case is not assigned to you.", "field_errors": {}}}, status=403)
        outreaches = Outreach.objects.filter(sample_case=case).prefetch_related("messages")
        return Response({
            "intro_channel": intro_channel(),
            "results": [{
                "id": o.id, "status": o.status, "status_label": o.get_status_display(), "channel": o.channel,
                "number": o.number_masked, "intro_sent_at": o.intro_sent_at, "reminded_at": o.reminded_at,
                "replied_at": o.replied_at, "sms_fallback_sent": o.sms_fallback_sent,
                "messages": [{"received_at": m.received_at, "body": m.body, "kind": m.kind, "auto_reply": m.auto_reply}
                             for m in o.messages.order_by("received_at")],
            } for o in outreaches],
        })

    def post(self, request):
        from .outreach import OutreachError, send_introduction

        case = get_object_or_404(SampleCase, sample_id=request.data.get("sample_id"))
        if getattr(request.user.role, "name", None) == "CONTACT_RA" and case.assigned_ra_id != request.user.id:
            return Response({"error": {"code": "forbidden", "message": "This case is not assigned to you.", "field_errors": {}}}, status=403)
        try:
            outreach = send_introduction(case, user=request.user)
        except OutreachError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        return Response({"id": outreach.id, "status": outreach.status, "channel": outreach.channel, "number": outreach.number_masked}, status=201)
