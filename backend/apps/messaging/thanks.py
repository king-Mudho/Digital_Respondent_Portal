"""Thanking participants who completed the study (PI, 18 Oct 2026), and recording whether they want the findings
summary, a workshop invitation, or both.

Who: a Main-400 or Reserve case whose questionnaire reached KoboToolbox (its link SUBMITTED or QA_PASSED, or the
case at S08-S11), and a KII record marked COMPLETED -- once each, never after consent was withdrawn, and never a
case or record marked to skip (metadata "thank_you" -> "skip", e.g. a possible test case the PI has to confirm).

How: on WhatsApp with the approved thank-you template (TWILIO_WA_CONTENT_THANK_YOU; its buttons are the choice), to
the number the questionnaire link went to; else by email with the PI's full text (the reply word is the choice); a
case with only a mobile waits until Meta approves the template. A run (send_due_thanks, every 30 minutes in the day)
also covers everyone who completed before this existed.

Where the choice goes: metadata["thank_you"]["preference"] on the case or KII record (BOTH / FINDINGS / WORKSHOP),
audited, so a mailing list for the findings and the workshop can be drawn from it.
"""

import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.audit.utils import log_action

from . import outbound
from . import twilio_client as tw
from .models import MessageChannel, MessagePurpose, ProviderMessage, ProviderStatus

logger = logging.getLogger(__name__)

KEY = "thank_you"
CHOICES = {
    # WhatsApp button ids and titles, and the words an email reply may use
    "THANKS_BOTH": "BOTH", "FINDINGS & WORKSHOP": "BOTH", "BOTH": "BOTH", "YES": "BOTH",
    "THANKS_FINDINGS": "FINDINGS", "FINDINGS ONLY": "FINDINGS", "FINDINGS": "FINDINGS",
    "THANKS_WORKSHOP": "WORKSHOP", "WORKSHOP ONLY": "WORKSHOP", "WORKSHOP": "WORKSHOP",
}
BUTTON_IDS = {"THANKS_BOTH", "THANKS_FINDINGS", "THANKS_WORKSHOP"}
LABEL = {"BOTH": "the findings summary and a workshop invitation", "FINDINGS": "the findings summary",
         "WORKSHOP": "a workshop invitation"}
SUBMITTED = ["SUBMITTED", "QA_PASSED"]
DONE_STATUSES = ["S08", "S09", "S10", "S11"]
GOOD = [ProviderStatus.SENT, ProviderStatus.DELIVERED, ProviderStatus.READ]


def choice_of(payload: str = "", body: str = "") -> str:
    """BOTH / FINDINGS / WORKSHOP from a button id, a button title or a one-word reply, else ""."""
    for text in (payload, body):
        words = " ".join((text or "").upper().replace("—", " ").replace("-", " ").split())
        if words in CHOICES:
            return CHOICES[words]
        first = words.split(" ")[0] if words else ""
        if first in ("BOTH", "FINDINGS", "WORKSHOP"):
            return first
    return ""


def is_button(payload: str) -> bool:
    return (payload or "").upper() in BUTTON_IDS


# --- Who is due ----------------------------------------------------------------------------------------------------

def _withdrawn(target) -> bool:
    from apps.consent.models import ConsentDecision, ConsentType
    from apps.consent.services import latest_consent

    record = latest_consent(target, ConsentType.PARTICIPATION)
    return record is not None and record.decision == ConsentDecision.WITHDRAWN


def due_cases():
    from apps.sampling.models import SampleCase

    return (SampleCase.objects.filter(Q(invitation_tokens__status__in=SUBMITTED) | Q(workflow_status__in=DONE_STATUSES))
            .exclude(metadata__has_key=KEY).distinct().select_related("organisation").order_by("pk"))


def due_records():
    from apps.kii.models import KIIRecord, KIIStatus

    return KIIRecord.objects.filter(status=KIIStatus.COMPLETED).exclude(metadata__has_key=KEY).order_by("pk")


# --- Where it goes -------------------------------------------------------------------------------------------------

def _invited_number(target) -> str:
    """The number the questionnaire or interview link went to on WhatsApp, else the target's own mobile."""
    from .matching import number_matching
    from .outreach import _kii_mobile, _mobile

    kii = hasattr(target, "kii_id")
    link = {"kii_record": target} if kii else {"sample_case": target}
    sent = (ProviderMessage.objects.filter(channel=MessageChannel.WHATSAPP, purpose=MessagePurpose.INVITATION, status__in=GOOD, **link)
            .order_by("-created_at").values_list("to_hash", flat=True).first())
    if sent:
        digits = number_matching(sent, None if kii else target, target if kii else None)
        if digits:
            return digits
    return _kii_mobile(target) if kii else _mobile(target)[0]


def _email(target) -> str:
    if hasattr(target, "kii_id"):
        return (target.email or "").strip()
    from apps.invitations.messages import recipients

    return recipients(target)["email_to"]


def _names(target) -> tuple[str, str, str]:
    """(who for the WhatsApp {{1}}, the email greeting, what they completed)."""
    if hasattr(target, "kii_id"):
        from apps.contacts.kii_finder import is_placeholder, organisation_name
        from .outreach import _kii_addressee

        org = organisation_name(target)
        greeting = (f"{org} team" if org else "Sir or Madam") if is_placeholder(target) else target.participant_name
        return _kii_addressee(target), greeting, "key informant interview"
    from apps.invitations.messages import _greeting_name, recipients

    org = target.organisation.name
    name = _greeting_name(recipients(target)["email_to_name"])
    return org, name or f"{org} team", "questionnaire"


def email_text(target) -> tuple[str, str]:
    """(subject, body): the PI's thank-you letter (18 Oct 2026); the reply word is their choice."""
    _, greeting, what = _names(target)
    responses = "interview responses" if what.startswith("key") else "questionnaire responses"
    body = (
        f"Dear {greeting},\n\n"
        f"Thank you for completing the {what} for my doctoral study at Chinhoyi University of Technology, which is "
        "developing and validating the Agribusiness Bankability Index (ABI) and the Agribusiness Bankability Framework "
        "for Food Systems Transformation (ABF-FST) in Zimbabwe.\n\n"
        "I appreciate the time and thought you devoted to sharing your organisation’s experiences. Your contribution "
        "will help ensure that the proposed tools reflect the practical financing needs, challenges and opportunities "
        "facing agribusinesses.\n\n"
        "Once the study is completed, I would be pleased to send you a summary of the findings and recommendations. "
        "Results will be presented in aggregate form, with appropriate safeguards to protect participants’ identities "
        "and confidential information.\n\n"
        "I also intend to organise a stakeholder workshop to present and discuss the findings. The workshop will provide "
        "an opportunity to consider their practical implications for agribusiness firms, finance houses, investors, "
        "government institutions and development organisations. The date, venue or online arrangements will be "
        "communicated once confirmed.\n\n"
        "If you would like to receive them, please reply to this email with one word:\n\n"
        "BOTH — the study findings and the workshop invitation\n"
        "FINDINGS — the findings summary only\n"
        "WORKSHOP — the workshop invitation only\n\n"
        "Receiving these communications and attending the workshop are optional and will not affect the treatment of "
        f"your {responses}. Your participation in the study does not constitute permission to identify you publicly.\n\n"
        "Thank you for helping build evidence to improve agribusiness financing and support food systems transformation "
        "in Zimbabwe.\n\n"
        "Yours sincerely,\n\n"
        "Happyson Saina\n"
        "PhD Researcher in Strategic Management\n"
        "Chinhoyi University of Technology\n\n"
        "Study website: https://agribizframework.com/\n"
        "Questions: Happyson Saina, 0773943709 | abffst.research@gmail.com"
    )
    return "Thank you for contributing to the Agribusiness Bankability Study", body


# --- Sending -------------------------------------------------------------------------------------------------------

def _mark(target, data: dict) -> None:
    target.metadata = {**(target.metadata or {}), KEY: {**(target.metadata or {}).get(KEY, {}), **data}}
    target.save(update_fields=["metadata", "updated_at"])


def thank(target, *, user=None) -> str:
    """Sends the thank-you once. Returns "whatsapp", "email", or why it was not sent ("waiting for the template",
    "no contact", "withdrawn", "already")."""
    if KEY in (target.metadata or {}):
        return "already"
    if _withdrawn(target):
        _mark(target, {"skip": "consent withdrawn"})
        return "withdrawn"
    kii = hasattr(target, "kii_id")
    link = {"kii_record": target} if kii else {"sample_case": target}
    ident = {"kii_id": target.kii_id} if kii else {"sample_id": target.sample_id}
    who, _, what = _names(target)
    template = (getattr(settings, "TWILIO_WA_CONTENT_THANK_YOU", "") or "").strip()
    number = _invited_number(target)
    if number and template and tw.content_approved(template):
        from .outreach import wording

        text = wording("thank_you_whatsapp")
        # 2026-10-21: the letter sits close to Meta's 1,024 characters, so most names took it over and Twilio failed it.
        values = outbound.fit_template(text, {1: who, 2: what})
        sent = outbound.send(channel=MessageChannel.WHATSAPP, number=number, purpose=MessagePurpose.THANK_YOU,
                             wa_content=template, wa_variables=values,
                             record_text=text.replace("{{1}}", values[1]).replace("{{2}}", values[2]),
                             user=user, **link)
        channel = "whatsapp"
    else:
        email = _email(target)
        if not email:
            return "waiting for the template" if number and template else "no contact"
        subject, body = email_text(target)
        sent = outbound.send_email(to=email, subject=subject, body=body, purpose=MessagePurpose.THANK_YOU, user=user, **link)
        channel = "email"
    _mark(target, {"sent_at": timezone.now().isoformat(), "channel": channel, "provider_message": sent.pk})
    log_action("participant.thanked", target, {**ident, "channel": channel, "recipient": sent.to_masked,
                                               "user_id": getattr(user, "id", None)}, user=user)
    return channel


def send_due_thanks(limit: int | None = None) -> dict:
    """The scheduled run: thank everyone who completed and has not been thanked. One failure never stops the rest;
    WhatsApp's daily limit stops WhatsApp for the day."""
    outcomes: dict[str, int] = {}
    targets = list(due_cases()) + list(due_records())
    for target in targets[:limit] if limit else targets:
        try:
            outcome = thank(target)
        except outbound.OutboundError as exc:
            outcome = exc.code
            if exc.code == "daily_limit_reached":
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                break
        except Exception:  # noqa: BLE001 -- e.g. the mail server refused one address
            logger.exception("Thank-you to %s failed", getattr(target, "sample_id", None) or getattr(target, "kii_id", ""))
            outcome = "failed"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return outcomes


# --- Their choice --------------------------------------------------------------------------------------------------

def record_choice(target, choice: str, *, via: str, message=None) -> None:
    """Keeps BOTH / FINDINGS / WORKSHOP on the case or record (the latest answer wins) and audits it."""
    if target is None or choice not in LABEL:
        return
    _mark(target, {"preference": choice, "preference_at": timezone.now().isoformat(), "preference_via": via})
    ident = {"kii_id": target.kii_id} if hasattr(target, "kii_id") else {"sample_id": target.sample_id}
    log_action("participant.follow_up_preference", target, {**ident, "preference": choice, "via": via,
                                                            "message": getattr(message, "pk", None)})


def acknowledgement(choice: str) -> str:
    return (f"Thank you, noted: we will send you {LABEL[choice]} when ready.\n\n"
            "Happyson Saina, PhD Researcher, Chinhoyi University of Technology")
