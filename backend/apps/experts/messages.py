"""An expert's invitation, ready for each channel, in the shape the admin send panel already renders for Main-400 and
KII invitations (InvitationSendPanel): WhatsApp opens the expert's chat with the message ready (no approved template
exists for experts, so the portal does not send WhatsApp itself), email goes from the study address, and the link and
code can be copied. Nothing here may contain a word respondents never see (AGENTS.md rule 2) -- checked by
test_experts."""

from django.utils import timezone

from apps.invitations.messages import portal_base

from .services import OPEN_TOKEN, ExpertError, verify_secret

STUDY_LINE = "Questions: Happyson Saina, 0773943709 | abffst.research@gmail.com"


def recipients(expert) -> dict:
    from apps.messaging.services import whatsapp_digits

    whatsapp = whatsapp_digits(expert.whatsapp_number) or whatsapp_digits(expert.phone)
    return {"whatsapp_to": whatsapp, "whatsapp_to_name": expert.full_name if whatsapp else "",
            "sms_to": whatsapp_digits(expert.phone) or whatsapp,
            "email_to": expert.email, "email_to_name": expert.full_name if expert.email else ""}


def build_messages(*, expert, link: str, manual_code: str, expires_at) -> dict:
    expires = timezone.localtime(expires_at).strftime("%d %B %Y").lstrip("0")
    who = f"{expert.title}, {expert.institution}" if expert.title and expert.institution else expert.institution or expert.title
    hello = f"Dear {expert.full_name}"
    whatsapp = (
        f"{hello}, you are invited to take part, as an expert, in reviewing the indicators of the Agribusiness "
        "Bankability Index (ABI), part of the ABF-FST doctoral study at Chinhoyi University of Technology. It takes "
        "about 15–20 minutes: you rate 16 proposed indicators for relevance, clarity and observability. Participation "
        "is voluntary.\n\n"
        f"Your personal link: {link}\n(valid until {expires})\n\n"
        f"If the link does not open, use code {manual_code}.\n\n{STUDY_LINE}"
    )
    sms = (f"ABF-FST study (Chinhoyi University of Technology): you are invited to review 16 ABI indicators as an expert "
           f"(15-20 min, voluntary). Your link: {link} (valid until {expires}). Code {manual_code}.")
    subject = "Invitation to review the Agribusiness Bankability Index (ABI) indicators as an expert"
    body = (
        f"{hello},\n\n"
        "My name is Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University of Technology.\n\n"
        + (f"In view of your expertise as {who}, I " if who else "I ")
        + "invite you to join a panel of twelve experts reviewing the proposed indicators of the Agribusiness Bankability "
        "Index (ABI), part of my study on the Agribusiness Bankability Framework for Food Systems Transformation "
        "(ABF-FST) in Zimbabwe.\n\n"
        "What does it involve?\n\n"
        "You rate 16 candidate indicators, in eight domains, on three short scales: how relevant, how clear and how "
        "practically verifiable each one is, with space for comments. It takes about 15–20 minutes. The exercise "
        "evaluates the proposed measures; it does not assess you, your institution or any borrower. A brief optional "
        "second round may follow for revised items.\n\n"
        "Voluntary participation and privacy\n\n"
        "Participation is voluntary, and you may skip any question or stop at any time without penalty. On the "
        "questionnaire you are identified only by an Expert ID, not your name; responses are reported in aggregate, "
        "and any attributed quotation would need your separate permission.\n\n"
        "Your personal link\n\n"
        f"{link}\n\n"
        f"The link is personal to you and valid until {expires}. It first shows the information for experts and asks "
        "for your consent; the questionnaire opens after that.\n\n"
        f"If the link does not open, go to the study portal and enter code {manual_code}.\n\n"
        "Thank you for considering this invitation.\n\n"
        "Happyson Saina\nPhD Researcher in Strategic Management\nChinhoyi University of Technology\n"
        f"{STUDY_LINE}"
    )
    return {"whatsapp": whatsapp, "sms": sms, "email_subject": subject, "email_body": body}


def check_own_link(token, link: str, manual_code: str) -> None:
    """The link and code must be this invitation's own and still open (as for KII and Main-400)."""
    if token.status not in OPEN_TOKEN or token.expires_at <= timezone.now():
        raise ExpertError("invitation_not_open", "This invitation is no longer open. Send a new one.", 409)
    raw = link.rstrip("/").rsplit("/ex/", 1)[-1] if "/ex/" in link else ""
    if not raw or not verify_secret(raw, token.token_hash) or portal_base(link) != link.split("/ex/", 1)[0]:
        raise ExpertError("link_mismatch", "That link doesn't belong to this invitation.")
    if not verify_secret(manual_code or "", token.manual_code_hash or ""):
        raise ExpertError("link_mismatch", "That code doesn't belong to this invitation.")


def _mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def email_invitation(token, *, link: str, manual_code: str, user) -> dict:
    from apps.audit.utils import log_action
    from apps.kobo.submission_copies import email_is_configured
    from apps.messaging import outbound
    from apps.messaging.models import MessagePurpose

    if not email_is_configured():
        raise ExpertError("email_not_configured", "Email isn't set up on the server yet. Use \"Open in email app\" instead.", 503)
    check_own_link(token, link, manual_code)
    expert = token.expert
    if not expert.email:
        raise ExpertError("no_email", "No email address is recorded for this expert. Add one on their record.")
    text = build_messages(expert=expert, link=link, manual_code=manual_code, expires_at=token.expires_at)
    outbound.send_email(to=expert.email, subject=text["email_subject"], body=text["email_body"],
                        purpose=MessagePurpose.INVITATION, user=user, redact_link=link, redact_code=manual_code)
    log_action("expert_invitation.emailed", token, {"expert_id": expert.expert_id, "recipient": _mask(expert.email),
                                                    "user_id": getattr(user, "id", None)}, user=user)
    return {"sent_to": _mask(expert.email)}
