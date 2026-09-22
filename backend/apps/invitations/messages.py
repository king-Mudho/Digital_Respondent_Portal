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
from django.core.mail import EmailMessage
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
        if not out["whatsapp_to"]:
            digits = whatsapp_digits(person.whatsapp_number or person.phone)
            if digits:
                out.update(whatsapp_to=digits, whatsapp_to_name=person.full_name)
        if not out["sms_to"]:
            digits = whatsapp_digits(person.phone or person.whatsapp_number)
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

    whatsapp = (
        "Hello. You are invited to take part in the ABF-FST research study at Chinhoyi University of "
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
    email_subject = "Invitation to take part in a Chinhoyi University of Technology research study"
    email_body = (
        f"Dear {name or 'Sir or Madam'},\n\n"
        f"{org} has been selected to take part in a doctoral research study, \"{STUDY_TITLE}\" (ABF-FST), "
        "conducted by Happyson Saina, Doctor of Strategic Management candidate at Chinhoyi University of "
        "Technology.\n\n"
        "Taking part is voluntary and takes about 15-25 minutes. Please use your personal link to read the "
        "study information, give your consent and take part:\n\n"
        f"{link}\n\n"
        f"This link is personal to your organisation and is valid until {expires}. If you would rather "
        "answer by phone or WhatsApp with a researcher, reply to this email or call 0773943709 and quote "
        f"code {manual_code}.\n\n"
        "The study produces no score, rating or financing decision, and individual answers are never "
        "shared with any lender or financial institution.\n\n"
        "Kind regards,\n"
        "ABF-FST research team\n"
        "Chinhoyi University of Technology\n"
        "Happyson Saina | 0773943709 | abffst.research@gmail.com"
    )
    return {"whatsapp": whatsapp, "sms": sms, "email_subject": email_subject, "email_body": email_body}


def _mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def email_invitation(token, *, link: str, manual_code: str, user) -> dict:
    """Send a just-issued invitation from the study address. The link must be
    this invitation's own (checked against the stored fingerprint), so the
    endpoint can't be used to email anything else."""
    from apps.audit.utils import log_action
    from apps.kobo.submission_copies import email_is_configured

    from .models import TokenStatus
    from .services import _verify_secret

    if not email_is_configured():
        raise InvitationSendError("email_not_configured", "Email isn't set up on the server yet. Use \"Open in email app\" instead.", 503)
    if token.status not in (TokenStatus.GENERATED, TokenStatus.SENT) or token.expires_at <= timezone.now():
        raise InvitationSendError("invitation_not_open", "This invitation is no longer open. Send a new one.", 409)
    raw = link.rstrip("/").rsplit("/i/", 1)[-1] if "/i/" in link else ""
    if not raw or not _verify_secret(raw, token.token_hash) or portal_base(link) != link.split("/i/", 1)[0]:
        raise InvitationSendError("link_mismatch", "That link doesn't belong to this invitation.", 400)
    if not _verify_secret(manual_code or "", token.manual_code_hash or ""):
        raise InvitationSendError("link_mismatch", "That code doesn't belong to this invitation.", 400)

    case = token.sample_case
    who = recipients(case)
    if not who["email_to"]:
        raise InvitationSendError("no_email", "No email address is recorded for this case. Add one under Respondents and contact details.")
    text = build_messages(sample_case=case, link=link, manual_code=manual_code, expires_at=token.expires_at,
                          to_name=who["email_to_name"])
    EmailMessage(
        subject=text["email_subject"], body=text["email_body"], from_email=settings.DEFAULT_FROM_EMAIL,
        to=[who["email_to"]], reply_to=[settings.STUDY_REPLY_TO_EMAIL] if settings.STUDY_REPLY_TO_EMAIL else None,
    ).send(fail_silently=False)
    log_action("invitation.emailed", token, {
        "sample_id": case.sample_id, "recipient": _mask(who["email_to"]), "user_id": getattr(user, "id", None),
    })
    return {"sent_to": _mask(who["email_to"])}
