"""Sending one SMS or WhatsApp message through Twilio, and recording what happened to it (2026-10-07).

The single place invitations (Main-400 and KII, one at a time and in batches) and automatic reminders go through, so
the daily caps, the "is this channel set up" check and the ProviderMessage record are applied the same way to all of
them. Callers check their own rules first: the invitation's own link, is_invitable(), the reminder sequence.
"""

from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action

from . import twilio_client as tw
from .models import MessageChannel, MessageStatus, ProviderMessage, ProviderStatus

TWILIO_STATUS = {
    "accepted": ProviderStatus.QUEUED, "scheduled": ProviderStatus.QUEUED, "queued": ProviderStatus.QUEUED,
    "sending": ProviderStatus.QUEUED, "sent": ProviderStatus.SENT, "delivered": ProviderStatus.DELIVERED,
    "read": ProviderStatus.READ, "undelivered": ProviderStatus.UNDELIVERED, "failed": ProviderStatus.FAILED,
    "canceled": ProviderStatus.FAILED,
}
PROGRESS = [ProviderStatus.QUEUED, ProviderStatus.SENT, ProviderStatus.DELIVERED, ProviderStatus.READ]
NOT_DELIVERED = [ProviderStatus.UNDELIVERED, ProviderStatus.FAILED]


class OutboundError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def daily_max(channel: str) -> int:
    name = "TWILIO_SMS_DAILY_MAX" if channel == MessageChannel.SMS else "TWILIO_WHATSAPP_DAILY_MAX"
    return max(0, int(getattr(settings, name, 0)))


def sent_today(channel: str) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return ProviderMessage.objects.filter(channel=channel, created_at__gte=start).count()


def left_today(channel: str) -> int:
    return max(0, daily_max(channel) - sent_today(channel))


def configured(channel: str, *, kii: bool = False) -> bool:
    return tw.sms_configured() if channel == MessageChannel.SMS else tw.whatsapp_configured(kii=kii)


def send(*, channel: str, number: str, purpose: str, sms_body: str = "", wa_content: str = "", wa_variables=None,
         user=None, **links) -> ProviderMessage:
    """Sends one message and records it. `links` names what it belongs to: sample_case or kii_record, and
    invitation_token, kii_invitation_token or message_log. Raises OutboundError with words a coordinator can act on."""
    label = "SMS" if channel == MessageChannel.SMS else "WhatsApp"
    if channel == MessageChannel.SMS and not tw.sms_configured():
        raise OutboundError("sms_not_configured", "SMS isn't set up on the server yet (deploy/configure-twilio.sh).", 503)
    if channel == MessageChannel.WHATSAPP and not (wa_content and tw.credentials_set() and settings.TWILIO_WHATSAPP_FROM.strip()):
        raise OutboundError("whatsapp_not_configured",
                            "WhatsApp sending isn't set up yet: it needs the Meta-approved sender and template (deploy/configure-twilio.sh).", 503)
    if not number:
        raise OutboundError("no_mobile", "No mobile number is on file (a landline can't receive SMS or WhatsApp). Add one under contact details.")
    if left_today(channel) < 1:
        raise OutboundError("daily_limit_reached", f"Today's limit of {daily_max(channel)} {label} messages has been reached. Try again tomorrow.", 409)
    try:
        if channel == MessageChannel.SMS:
            result = tw.send_sms(number, sms_body)
        else:
            result = tw.send_whatsapp(number, wa_content, wa_variables)
    except tw.TwilioError as exc:
        raise OutboundError("twilio_refused", f"The {label} message was not sent: {exc}", 502) from exc
    segments = result.get("num_segments")
    return ProviderMessage.objects.create(
        channel=channel, purpose=purpose, provider_sid=result.get("sid") or None, to_masked=tw.mask(number),
        status=TWILIO_STATUS.get(str(result.get("status", "")).lower(), ProviderStatus.QUEUED),
        segments=int(segments) if str(segments or "").isdigit() else None, sent_by=user, **links,
    )


def record_status(params: dict) -> bool:
    """Applies one Twilio status callback. Delivery reports can arrive out of order ("sent" after "delivered"), so a
    message only moves forward; not delivered is final. A reminder Twilio could not deliver is marked FAILED on its
    MessageLog, which puts it back on Follow-ups for a person rather than counting toward Nonresponse."""
    message = ProviderMessage.objects.select_related("message_log").filter(provider_sid=params.get("MessageSid") or None).first()
    if message is None:
        return False
    new = TWILIO_STATUS.get(str(params.get("MessageStatus", "")).lower())
    if new is None or message.status in NOT_DELIVERED or new == message.status:
        return True
    if new not in NOT_DELIVERED and PROGRESS.index(new) < PROGRESS.index(message.status):
        return True
    message.status = new
    message.error_code = str(params.get("ErrorCode") or "")[:16]
    message.error_message = str(params.get("ErrorMessage") or "")[:300]
    message.save(update_fields=["status", "error_code", "error_message", "updated_at"])
    if new in NOT_DELIVERED:
        if message.message_log_id:
            message.message_log.status = MessageStatus.FAILED
            message.message_log.save(update_fields=["status"])
        log_action("twilio.message_failed", message.sample_case or message.kii_record or message, {
            "channel": message.channel, "purpose": message.purpose, "recipient": message.to_masked,
            "error_code": message.error_code, "provider_message": message.pk,
        })
    return True
