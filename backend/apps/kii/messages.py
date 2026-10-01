"""
A KII self-service invitation, ready to send on each channel -- the KII
equivalent of apps.invitations.messages, simplified because a KIIRecord has
exactly one informant with its own phone/whatsapp_number/email fields, not a
set of Respondent rows to pick the best contact from.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.invitations.messages import CONTACT_LINE, STUDY_TITLE, portal_base


class KIIInvitationSendError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def kii_recipients(kii_record) -> dict:
    """Same field names as apps.invitations.messages.recipients() (whatsapp_to_name/
    email_to_name, not a single to_name) so the admin frontend's existing
    InvitationSendPanel component can render this response unmodified."""
    from apps.messaging.services import whatsapp_digits

    whatsapp = whatsapp_digits(kii_record.whatsapp_number or kii_record.phone)
    sms = whatsapp_digits(kii_record.phone or kii_record.whatsapp_number)
    name = kii_record.participant_name
    return {
        "whatsapp_to": whatsapp, "whatsapp_to_name": name if whatsapp else "",
        "sms_to": sms,
        "email_to": kii_record.email, "email_to_name": name if kii_record.email else "",
    }


def build_kii_messages(*, kii_record, link: str, manual_code: str, expires_at) -> dict:
    expires = timezone.localtime(expires_at).strftime("%d %B %Y").lstrip("0")
    name = kii_record.participant_name

    whatsapp = (
        f"Hello {name}. You are invited to take part in a confidential interview for the ABF-FST research "
        "study at Chinhoyi University of Technology. Taking part is voluntary, and you can complete it in "
        "your own time using the link below.\n\n"
        f"Your personal link: {link}\n(valid until {expires})\n\n"
        f"Prefer to answer by phone instead? Reply to this message and quote code {manual_code}.\n\n"
        f"{CONTACT_LINE}"
    )
    sms = (
        f"ABF-FST research study (Chinhoyi University of Technology): you are invited to an interview. "
        f"Voluntary. Your personal link: {link} (valid until {expires}). "
        f"Prefer a call? Ring 0773943709 and quote code {manual_code}."
    )
    email_subject = "Invitation to a Chinhoyi University of Technology research interview"
    email_body = (
        f"Dear {name},\n\n"
        f"You have been invited to take part in a Key Informant Interview for the doctoral research study, "
        f"\"{STUDY_TITLE}\" (ABF-FST), conducted by Happyson Saina, Doctor of Strategic Management candidate "
        "at Chinhoyi University of Technology.\n\n"
        "Taking part is voluntary. Please use your personal link to read the study information, give your "
        "consent and complete the interview in your own time:\n\n"
        f"{link}\n\n"
        f"This link is personal to you and is valid until {expires}. If you would rather answer by phone or "
        f"WhatsApp with a researcher, reply to this email or call 0773943709 and quote code {manual_code}.\n\n"
        "The study produces no score, rating or financing decision.\n\n"
        "Kind regards,\n"
        "ABF-FST research team\n"
        "Chinhoyi University of Technology\n"
        "Happyson Saina | 0773943709 | abffst.research@gmail.com"
    )
    return {"whatsapp": whatsapp, "sms": sms, "email_subject": email_subject, "email_body": email_body}


def _mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def email_kii_invitation(token, *, link: str, manual_code: str, user) -> dict:
    """Send a just-issued KII invitation from the study address. The link must
    be this invitation's own (checked against the stored fingerprint), the
    same ownership check as apps.invitations.messages.email_invitation."""
    from apps.audit.utils import log_action
    from apps.kobo.submission_copies import email_is_configured

    from .models import KIIInvitationTokenStatus
    from .services import _verify_secret

    if not email_is_configured():
        raise KIIInvitationSendError("email_not_configured", "Email isn't set up on the server yet. Use \"Open in email app\" instead.", 503)
    if token.status not in (KIIInvitationTokenStatus.GENERATED, KIIInvitationTokenStatus.SENT) or token.expires_at <= timezone.now():
        raise KIIInvitationSendError("invitation_not_open", "This invitation is no longer open. Send a new one.", 409)
    raw = link.rstrip("/").rsplit("/ki/", 1)[-1] if "/ki/" in link else ""
    if not raw or not _verify_secret(raw, token.token_hash) or portal_base(link) != link.split("/ki/", 1)[0]:
        raise KIIInvitationSendError("link_mismatch", "That link doesn't belong to this invitation.", 400)
    if not _verify_secret(manual_code or "", token.manual_code_hash or ""):
        raise KIIInvitationSendError("link_mismatch", "That code doesn't belong to this invitation.", 400)

    record = token.kii_record
    who = kii_recipients(record)
    if not who["email_to"]:
        raise KIIInvitationSendError("no_email", "No email address is recorded for this informant. Add one on the KII record.")
    text = build_kii_messages(kii_record=record, link=link, manual_code=manual_code, expires_at=token.expires_at)
    EmailMessage(
        subject=text["email_subject"], body=text["email_body"], from_email=settings.DEFAULT_FROM_EMAIL,
        to=[who["email_to"]], reply_to=[settings.STUDY_REPLY_TO_EMAIL] if settings.STUDY_REPLY_TO_EMAIL else None,
    ).send(fail_silently=False)
    log_action("kii_invitation.emailed", token, {
        "kii_id": record.kii_id, "recipient": _mask(who["email_to"]), "user_id": getattr(user, "id", None),
    })
    return {"sent_to": _mask(who["email_to"])}
