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

    # Mobiles only (whatsapp_digits gives "" for a landline), from either field.
    whatsapp = whatsapp_digits(kii_record.whatsapp_number) or whatsapp_digits(kii_record.phone)
    sms = whatsapp_digits(kii_record.phone) or whatsapp_digits(kii_record.whatsapp_number)
    name = kii_record.participant_name
    return {
        "whatsapp_to": whatsapp, "whatsapp_to_name": name if whatsapp else "",
        "sms_to": sms,
        "email_to": kii_record.email, "email_to_name": name if kii_record.email else "",
    }


def build_kii_messages(*, kii_record, link: str, manual_code: str, expires_at) -> dict:
    """Names the informant's organisation (PI request, 2026-10-06), so the informant and the sender can both tell
    which organisation it is. A record still "<Organisation> (contact not yet identified)" goes to the organisation,
    not a person: it is greeted by the organisation's name and says which role the study would like to interview,
    instead of greeting "CBZ Bank (contact not yet identified)" by name."""
    from apps.contacts.kii_finder import is_placeholder, organisation_name

    expires = timezone.localtime(expires_at).strftime("%d %B %Y").lstrip("0")
    org = organisation_name(kii_record)
    blank = is_placeholder(kii_record)
    name = "" if blank else kii_record.participant_name
    if blank:
        hello = f"Hello, {org}." if org else "Hello."
        role_line = f"We would like to interview the person who holds the role of {kii_record.participant_role}. "
        sms_who = f"{org} is" if org else "you are"
    else:
        hello = f"Hello {name} ({org})." if org else f"Hello {name}."
        role_line = ""
        sms_who = f"{name} of {org}, you are" if org else "you are"

    whatsapp = (
        f"{hello} You are invited to take part in a confidential interview for the ABF-FST research "
        f"study at Chinhoyi University of Technology. {role_line}Taking part is voluntary, and you can complete "
        "it in your own time using the link below.\n\n"
        f"Your personal link: {link}\n(valid until {expires})\n\n"
        f"Prefer to answer by phone instead? Reply to this message and quote code {manual_code}.\n\n"
        f"{CONTACT_LINE}"
    )
    sms = (
        f"ABF-FST research study (Chinhoyi University of Technology): {sms_who} invited to an interview. "
        f"Voluntary. Your personal link: {link} (valid until {expires}). "
        f"Prefer a call? Ring 0773943709 and quote code {manual_code}."
    )
    email_subject = (f"{org}: " if org else "") + "invitation to a Chinhoyi University of Technology research interview"
    if blank:
        invited = f"{org} is invited to take part" if org else "You are invited to take part"
    else:
        invited = f"You have been invited, as {kii_record.participant_role} at {org}, to take part" if org else "You have been invited to take part"
    email_body = (
        f"Dear {name or 'Sir or Madam'},\n\n"
        f"{invited} in a Key Informant Interview for the doctoral research study, "
        f"\"{STUDY_TITLE}\" (ABF-FST), conducted by Happyson Saina, Doctor of Strategic Management candidate "
        f"at Chinhoyi University of Technology.{(' ' + role_line.strip()) if role_line else ''}\n\n"
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


def _check_own_kii_link(token, link: str, manual_code: str) -> None:
    """The KII equivalent of apps.invitations.messages._check_own_link: the link and code must be this invitation's
    own and still working. Shared by email, SMS and WhatsApp."""
    from .models import KIIInvitationTokenStatus
    from .services import _verify_secret

    # Any link that still works (2026-10-06): the same invitation on a second channel, as for Main-400.
    still_open = (KIIInvitationTokenStatus.GENERATED, KIIInvitationTokenStatus.SENT, KIIInvitationTokenStatus.OPENED,
                  KIIInvitationTokenStatus.CONSENTED, KIIInvitationTokenStatus.STARTED)
    if token.status not in still_open or token.expires_at <= timezone.now():
        raise KIIInvitationSendError("invitation_not_open", "This invitation is no longer open. Send a new one.", 409)
    raw = link.rstrip("/").rsplit("/ki/", 1)[-1] if "/ki/" in link else ""
    if not raw or not _verify_secret(raw, token.token_hash) or portal_base(link) != link.split("/ki/", 1)[0]:
        raise KIIInvitationSendError("link_mismatch", "That link doesn't belong to this invitation.", 400)
    if not _verify_secret(manual_code or "", token.manual_code_hash or ""):
        raise KIIInvitationSendError("link_mismatch", "That code doesn't belong to this invitation.", 400)


def text_kii_invitation(token, *, channel: str, link: str, manual_code: str, user) -> dict:
    """Send an issued KII invitation by SMS or WhatsApp through Twilio (2026-10-07). WhatsApp fills the KII template
    with who it is for (the named informant and organisation, or the organisation alone while the contact is still a
    placeholder), the link, expiry date and code."""
    from apps.audit.utils import log_action
    from apps.contacts.kii_finder import is_placeholder, organisation_name
    from apps.messaging import outbound
    from apps.messaging.models import MessageChannel, MessagePurpose

    _check_own_kii_link(token, link, manual_code)
    record = token.kii_record
    who = kii_recipients(record)
    number = who["sms_to"] if channel == MessageChannel.SMS else who["whatsapp_to"]
    org = organisation_name(record)
    addressee = org if is_placeholder(record) else (f"{record.participant_name} ({org})" if org else record.participant_name)
    text = build_kii_messages(kii_record=record, link=link, manual_code=manual_code, expires_at=token.expires_at)
    expires = timezone.localtime(token.expires_at).strftime("%d %B %Y").lstrip("0")
    try:
        message = outbound.send(
            channel=channel, number=number, purpose=MessagePurpose.INVITATION, sms_body=text["sms"],
            wa_content=settings.TWILIO_WA_CONTENT_KII_INVITATION.strip(),
            wa_variables={1: addressee or "colleague", 2: link, 3: expires, 4: manual_code},
            user=user, kii_record=record, kii_invitation_token=token,
        )
    except outbound.OutboundError as exc:
        raise KIIInvitationSendError(exc.code, str(exc), exc.status) from exc
    action = "kii_invitation.sms_sent" if channel == MessageChannel.SMS else "kii_invitation.whatsapp_sent"
    log_action(action, token, {
        "kii_id": record.kii_id, "recipient": message.to_masked, "provider_message": message.pk,
        "user_id": getattr(user, "id", None),
    }, user=user)
    return {"sent_to": message.to_masked, "status": message.status}


def email_kii_invitation(token, *, link: str, manual_code: str, user) -> dict:
    """Send a just-issued KII invitation from the study address. The link must
    be this invitation's own (checked against the stored fingerprint), the
    same ownership check as apps.invitations.messages.email_invitation."""
    from apps.audit.utils import log_action
    from apps.kobo.submission_copies import email_is_configured

    if not email_is_configured():
        raise KIIInvitationSendError("email_not_configured", "Email isn't set up on the server yet. Use \"Open in email app\" instead.", 503)
    _check_own_kii_link(token, link, manual_code)

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
