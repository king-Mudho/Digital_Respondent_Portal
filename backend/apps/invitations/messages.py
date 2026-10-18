"""
The invitation, ready to send on each channel (added 2026-09-16).

One place writes every version -- WhatsApp, SMS, email -- so what an RA
sends by hand, what the portal emails from the study address, and what the
manuals describe never drift apart. Each carries the personal link, its
expiry, the manual code for phone help, and the study contact line the
Participant Information Sheet refers to ("the same details are also
included in your invitation message").
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMessage  # noqa: F401 -- tests patch EmailMessage.send through this module
from django.utils import timezone

CONTACT_LINE = "Questions: Happyson Saina, 0773943709, abffst.research@gmail.com"
STUDY_TITLE = ("Developing and Validating the Agribusiness Bankability Framework for Food Systems "
               "Transformation through Novel Financing Models in Zimbabwe")


class InvitationSendError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def portal_base(requested: str | None) -> str:
    """Where respondent links point. The page that issued the invitation
    says where it is running; it is used only if it is the study domain (or
    a local development address), never an arbitrary site."""
    fallback = f"https://{settings.APP_DOMAIN}"
    if not requested:
        return fallback
    parts = urlsplit(requested)
    host = (parts.hostname or "").lower()
    allowed = host == settings.APP_DOMAIN.lower() or (settings.DEBUG and host in ("localhost", "127.0.0.1"))
    if parts.scheme not in ("http", "https") or not allowed:
        return fallback
    return f"{parts.scheme}://{parts.netloc}"


def recipients(sample_case) -> dict:
    """Who each channel goes to: the case's respondent, eligible first."""
    from apps.messaging.services import whatsapp_digits

    people = sorted(sample_case.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))
    out = {"whatsapp_to": "", "whatsapp_to_name": "", "sms_to": "", "email_to": "", "email_to_name": ""}
    for person in people:
        # Mobiles only (whatsapp_digits gives "" for a landline), from either field.
        if not out["whatsapp_to"]:
            digits = whatsapp_digits(person.whatsapp_number) or whatsapp_digits(person.phone)
            if digits:
                out.update(whatsapp_to=digits, whatsapp_to_name=person.full_name)
        if not out["sms_to"]:
            digits = whatsapp_digits(person.phone) or whatsapp_digits(person.whatsapp_number)
            if digits:
                out["sms_to"] = digits
        if not out["email_to"] and person.email:
            out.update(email_to=person.email, email_to_name=person.full_name)
    return out


def _greeting_name(name: str) -> str:
    placeholder = name.startswith(("Organisation contact", "Contact to be"))
    return name if name and not placeholder else ""


def build_messages(*, sample_case, link: str, manual_code: str, expires_at, to_name: str = "") -> dict:
    expires = timezone.localtime(expires_at).strftime("%d %B %Y").lstrip("0")
    org = sample_case.organisation.name
    name = _greeting_name(to_name)

    # The organisation is named first (PI request, 2026-10-06), so whoever reads it -- and whoever sent it, scrolling
    # back through the study phone -- can tell at a glance which organisation the link belongs to.
    whatsapp = (
        f"Hello, {org}. You are invited to take part in the ABF-FST research study at Chinhoyi University of "
        "Technology on agribusiness financing in Zimbabwe. Taking part is voluntary.\n\n"
        f"Your personal link: {link}\n(valid until {expires})\n\n"
        f"Prefer to answer by phone? Reply to this message and quote code {manual_code}.\n\n"
        f"{CONTACT_LINE}"
    )
    sms = (
        f"ABF-FST research study (Chinhoyi University of Technology): {org} is invited to take part. "
        f"Voluntary, about 15-25 min. Your personal link: {link} (valid until {expires}). "
        f"Prefer a call? Ring 0773943709 and quote code {manual_code}."
    )
    # The PI's own invitation text (approved 18 Oct 2026). In an email the personal link takes the place of
    # WhatsApp's "May I send you the link?".
    email_subject = f"{org}: invitation to participate in research on agribusiness access to finance in Zimbabwe"
    email_body = (
        f"Dear {name or org + ' team'},\n\n"
        "My name is Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University of Technology.\n\n"
        f"{org} has been selected for my study on how financing models can improve agribusiness access to suitable "
        "finance and support food systems transformation in Zimbabwe, and I invite a knowledgeable representative of "
        "your organisation to participate.\n\n"
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
        "Participation involves a questionnaire of about 15-25 minutes on agribusiness financing experiences, "
        "opportunities and constraints, completed through your personal link below. If you would rather answer by "
        f"phone or WhatsApp with a researcher, reply to this email or call 0773943709 and quote code {manual_code}.\n\n"
        "The participant information sheet, which opens first from your link, explains the topics, data handling "
        "arrangements, withdrawal provisions and researcher contact details before you decide whether to participate.\n\n"
        "Voluntary participation and confidentiality\n\n"
        "Participation is entirely voluntary. You may decline, skip questions or stop at any time without penalty. Responses will "
        "be treated confidentially in accordance with the participant information sheet. Any audio recording would "
        "require your separate permission.\n\n"
        "This is an academic study. Participation is not a funding application, credit assessment or a promise of "
        "access to finance. The ABI is still undergoing development and validation.\n\n"
        "You can explore the study\u2019s background here:\nhttps://agribizframework.com/\n\n"
        "Your personal link\n\n"
        f"{link}\n\n"
        f"This link is personal to your organisation and is valid until {expires}. Your informed consent is requested on the "
        "link, after you have read the information and before the questionnaire begins.\n\n"
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


def _check_own_link(token, link: str, manual_code: str) -> None:
    """The link and code must be this invitation's own (checked against the stored fingerprints) and still working, so
    a send endpoint can't be used to send anything else. Shared by email, SMS and WhatsApp."""
    from .batch import OPEN_STATUSES
    from .services import _verify_secret

    if token.status not in OPEN_STATUSES or token.expires_at <= timezone.now():
        raise InvitationSendError("invitation_not_open", "This invitation is no longer open. Send a new one.", 409)
    raw = link.rstrip("/").rsplit("/i/", 1)[-1] if "/i/" in link else ""
    if not raw or not _verify_secret(raw, token.token_hash) or portal_base(link) != link.split("/i/", 1)[0]:
        raise InvitationSendError("link_mismatch", "That link doesn't belong to this invitation.", 400)
    if not _verify_secret(manual_code or "", token.manual_code_hash or ""):
        raise InvitationSendError("link_mismatch", "That code doesn't belong to this invitation.", 400)


def text_invitation(token, *, channel: str, link: str, manual_code: str, user) -> dict:
    """Send an issued invitation by SMS or WhatsApp through Twilio (2026-10-07): the same link and code as every other
    channel, to the case's mobile (recipients() gives mobiles only). SMS carries build_messages()' SMS wording;
    WhatsApp the Meta-approved template, filled with the organisation, link, expiry date and code."""
    from apps.audit.utils import log_action
    from apps.messaging import outbound
    from apps.messaging.models import MessageChannel, MessagePurpose

    _check_own_link(token, link, manual_code)
    case = token.sample_case
    who = recipients(case)
    number = who["sms_to"] if channel == MessageChannel.SMS else who["whatsapp_to"]
    text = build_messages(sample_case=case, link=link, manual_code=manual_code, expires_at=token.expires_at,
                          to_name=who["whatsapp_to_name"])
    expires = timezone.localtime(token.expires_at).strftime("%d %B %Y").lstrip("0")
    try:
        message = outbound.send(
            channel=channel, number=number, purpose=MessagePurpose.INVITATION, sms_body=text["sms"],
            wa_content=settings.TWILIO_WA_CONTENT_INVITATION.strip(),
            wa_variables={1: case.organisation.name, 2: link, 3: expires, 4: manual_code},
            user=user, sample_case=case, invitation_token=token,
            record_text=text["whatsapp"], redact_link=link, redact_code=manual_code,
        )
    except outbound.OutboundError as exc:
        raise InvitationSendError(exc.code, str(exc), exc.status) from exc
    action = "invitation.sms_sent" if channel == MessageChannel.SMS else "invitation.whatsapp_sent"
    log_action(action, token, {
        "sample_id": case.sample_id, "recipient": message.to_masked, "provider_message": message.pk,
        "user_id": getattr(user, "id", None),
    }, user=user)
    return {"sent_to": message.to_masked, "status": message.status}


def email_invitation(token, *, link: str, manual_code: str, user) -> dict:
    """Send a just-issued invitation from the study address. The link must be
    this invitation's own (checked against the stored fingerprint), so the
    endpoint can't be used to email anything else.

    Any invitation whose link still works can be emailed, not only one still at SENT: it is the same link sent on a
    second channel. Until 2026-10-06 a respondent tapping the WhatsApp link a minute earlier (OPENED) made the email
    refuse with "no longer open", and the only way on was a new invitation, which killed the WhatsApp link."""
    from apps.audit.utils import log_action
    from apps.kobo.submission_copies import email_is_configured
    from apps.messaging import outbound
    from apps.messaging.models import MessagePurpose

    if not email_is_configured():
        raise InvitationSendError("email_not_configured", "Email isn't set up on the server yet. Use \"Open in email app\" instead.", 503)
    _check_own_link(token, link, manual_code)

    case = token.sample_case
    who = recipients(case)
    if not who["email_to"]:
        raise InvitationSendError("no_email", "No email address is recorded for this case. Add one under Respondents and contact details.")
    text = build_messages(sample_case=case, link=link, manual_code=manual_code, expires_at=token.expires_at,
                          to_name=who["email_to_name"])
    outbound.send_email(
        to=who["email_to"], subject=text["email_subject"], body=text["email_body"], purpose=MessagePurpose.INVITATION,
        user=user, sample_case=case, invitation_token=token, redact_link=link, redact_code=manual_code,
    )
    log_action("invitation.emailed", token, {
        "sample_id": case.sample_id, "recipient": _mask(who["email_to"]), "user_id": getattr(user, "id", None),
    })
    return {"sent_to": _mask(who["email_to"])}
