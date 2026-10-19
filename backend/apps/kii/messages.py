"""
A KII self-service invitation, ready to send on each channel -- the KII
equivalent of apps.invitations.messages, simplified because a KIIRecord has
exactly one informant with its own phone/whatsapp_number/email fields, not a
set of Respondent rows to pick the best contact from.
"""

from django.conf import settings
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


def build_kii_messages(*, kii_record, link: str, manual_code: str, expires_at, letters=()) -> dict:
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
    # The PI's own invitation text (approved 18 Oct 2026). In an email the personal link takes the place of
    # WhatsApp's "May I send you the link?".
    email_subject = (f"{org}: " if org else "") + "invitation to participate in research on agribusiness access to finance in Zimbabwe"
    if blank:
        invite = (f"I invite a knowledgeable representative of {org or 'your organisation'}, ideally the person who holds "
                  f"the role of {kii_record.participant_role}, to participate")
    else:
        invite = f"I invite you, as {kii_record.participant_role} at {org}, to participate" if org else "I invite you to participate"
    email_body = (
        f"Dear {name or (org + ' team' if org else 'Sir or Madam')},\n\n"
        "My name is Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University of Technology.\n\n"
        f"{invite} in my study on how financing models can improve agribusiness access to suitable finance and support "
        "food systems transformation in Zimbabwe.\n\n"
        + (f"So that you can confirm this study is genuine, its research clearance letters are attached: {'; '.join(letters)}.\n\n"
           if letters else "") +
        "What is the purpose of the study?\n\n"
        "The study is developing and validating two practical research tools:\n\n"
        "\u2022 Agribusiness Bankability Index (ABI): intended to help assess an enterprise\u2019s readiness to access and use "
        "finance, and identify areas requiring improvement.\n\n"
        "\u2022 Agribusiness Bankability Framework for Food Systems Transformation (ABF-FST): intended to explain how "
        "enterprise capabilities, financing arrangements and the institutional environment can support stronger "
        "agricultural and food businesses.\n\n"
        "Food systems transformation includes improvements in production, processing, storage, distribution and markets "
        "that contribute to more reliable food supplies, viable businesses and livelihoods.\n\n"
        "Why does your participation matter?\n\n"
        "Your organisation\u2019s practical experience can help identify what enables or prevents agribusinesses from "
        "obtaining suitable finance. We need perspectives from organisations with different experiences\u2014including "
        "those that have accessed finance, struggled to obtain it or chosen other financing arrangements.\n\n"
        "Your contribution can help ensure that the proposed tools reflect business realities. The findings may inform "
        "enterprise support, financial-product design, investment preparation, government policy and development "
        "programmes. These are potential uses of the research, rather than promised benefits to individual "
        "participants.\n\n"
        "You may request a summary of the findings when the study is complete.\n\n"
        "What would participation involve?\n\n"
        "Participation involves approximately 30 minutes of discussion about agribusiness financing experiences, "
        "opportunities and constraints. You may provide written responses through your personal link below, or arrange "
        f"a telephone interview: reply to this email or call 0773943709 and quote code {manual_code}.\n\n"
        "The participant information sheet, which opens first from your link, explains the topics, data handling "
        "arrangements, withdrawal provisions and researcher contact details before you decide whether to participate.\n\n"
        "Voluntary participation and confidentiality\n\n"
        "Participation is entirely voluntary. You may decline, skip questions or stop the interview without penalty. Responses will "
        "be treated confidentially in accordance with the participant information sheet. Any audio recording would "
        "require your separate permission.\n\n"
        "This is an academic study. Participation is not a funding application, credit assessment or a promise of "
        "access to finance. The ABI is still undergoing development and validation.\n\n"
        "You can explore the study\u2019s background here:\nhttps://agribizframework.com/\n\n"
        "Your personal link\n\n"
        f"{link}\n\n"
        f"This link is personal to you and is valid until {expires}. Your informed consent is requested on the "
        "link, after you have read the information and before the interview begins.\n\n"
        "Thank you for considering this invitation.\n\n"
        "Happyson Saina\n"
        "PhD Researcher in Strategic Management\n"
        "Chinhoyi University of Technology\n"
        "Questions: Happyson Saina, 0773943709 | abffst.research@gmail.com"
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
            record_text=text["whatsapp"], redact_link=link, redact_code=manual_code,
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
    from apps.clearance.services import letter_attachments, respondent_letters

    # The study's clearance letters go with the invitation (PI, 19 Oct 2026).
    letters = [d.title for d in respondent_letters()]
    text = build_kii_messages(kii_record=record, link=link, manual_code=manual_code, expires_at=token.expires_at,
                              letters=letters)
    from apps.messaging import outbound
    from apps.messaging.models import MessagePurpose

    outbound.send_email(
        to=who["email_to"], subject=text["email_subject"], body=text["email_body"], purpose=MessagePurpose.INVITATION,
        user=user, kii_record=record, kii_invitation_token=token, redact_link=link, redact_code=manual_code,
        attachments=letter_attachments() if letters else (),
    )
    log_action("kii_invitation.emailed", token, {
        "kii_id": record.kii_id, "recipient": _mask(who["email_to"]), "user_id": getattr(user, "id", None),
    })
    return {"sent_to": _mask(who["email_to"])}
