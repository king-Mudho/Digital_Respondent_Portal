"""Ask first, then invite (PI decision, 2026-10-07).

Instead of sending the invitation link straight away, the portal can first send an organisation a short introduction
to the study asking whether it will take part. The reply decides what happens next:

- YES: the invitation is issued (issue_invitation(): is_invitable() and the move to S05 still apply, AGENTS.md rule 4)
  and its approved WhatsApp text, with the personal link and code, goes back in the same chat. The person has asked
  for it, which is what WhatsApp's opt-in rule wants, and it is a free-text reply inside the 24 hours WhatsApp allows
  after their message.
- NO or STOP: the refusal is recorded -- the case moves to S12 Refused (PI decision) and any open invitation is revoked
  -- with one acknowledgement.
- Anything else: one automatic answer a day with the study contact, and the message waits in Conversations for a person.

Replies only ever arrive on WhatsApp: Twilio cannot receive SMS in Zimbabwe. So an SMS introduction (the fallback when
WhatsApp is not set up or does not deliver) carries a tap-to-reply link to the study's WhatsApp number.

A YES or NO is read only from the quick-reply button or a whole message that is one of the configured words
(OUTREACH_YES_WORDS / OUTREACH_NO_WORDS), so "no problem" is never taken as a refusal.

KII informants are asked first the same way (PI request, 2026-10-14), with their own introduction addressed to the named
informant and organisation: a YES issues the KII self-service link (issue_kii_invitation(): PROSPECT -> INVITED) and
sends it back in the chat, a NO records the record as DECLINED and revokes any open link. Reminders, the SMS fallback
and the "phone them" list work as for Main-400 cases. An Outreach belongs to exactly one case or KII record.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.audit.utils import log_action

from . import outbound
from . import twilio_client as tw
from .hashing import number_hash
from .models import (
    OPEN_OUTREACH,
    InboundMessage,
    MessageChannel,
    MessagePurpose,
    MessageTemplate,
    Outreach,
    OutreachStatus,
    ReplyKind,
)

logger = logging.getLogger(__name__)

# Statuses that mean the case has had its introduction and is not to be introduced again.
INTRODUCED = [OutreachStatus.INTRO_SENT, OutreachStatus.REMINDED, OutreachStatus.ACCEPTED, OutreachStatus.DECLINED]
# A late YES or NO still counts after the case was listed for a phone call.
ANSWERABLE = [*OPEN_OUTREACH, OutreachStatus.NO_REPLY, OutreachStatus.NOT_DELIVERED]


class OutreachError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)



def wording(name: str, org: str = "") -> str:
    template = MessageTemplate.objects.filter(name=name).first()
    body = template.body if template else ""
    return body.replace("{org}", org).replace("{wa_link}", tw.study_whatsapp_link())


def intro_channel(*, kii: bool = False) -> str | None:
    """How an introduction goes out today: the approved WhatsApp template, else an SMS carrying the tap-to-reply
    WhatsApp link. Without the study's WhatsApp number no reply could ever arrive, so nothing is offered. KII
    informants have their own template."""
    if not (tw.credentials_set() and (settings.TWILIO_WHATSAPP_FROM or "").strip()):
        return None
    setting = "TWILIO_WA_CONTENT_KII_INTRO" if kii else "TWILIO_WA_CONTENT_INTRO"
    if (getattr(settings, setting, "") or "").strip() and not tw.template_waiting(setting):
        return MessageChannel.WHATSAPP  # only once Meta has approved it; until then the SMS with the reply link
    return MessageChannel.SMS if tw.sms_configured() else None


def introduction_candidates():
    """Verified cases that may be invited, with a number on file, no open invitation, and no introduction yet."""
    from apps.invitations.batch import batch_candidates

    introduced = Outreach.objects.filter(sample_case=OuterRef("pk"), status__in=INTRODUCED)
    return batch_candidates(("SMS", "WHATSAPP")).exclude(Exists(introduced))


def _mobile(case) -> tuple[str, object]:
    """The case's mobile (eligible respondent first, as recipients() picks it) and the respondent it belongs to."""
    from apps.invitations.messages import recipients
    from apps.messaging.services import whatsapp_digits

    number = recipients(case)["whatsapp_to"]
    for person in sorted(case.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id)):
        if number and number in (whatsapp_digits(person.whatsapp_number), whatsapp_digits(person.phone)):
            return number, person
    return number, None


def _send_intro(case, number: str, channel: str, *, reminder: bool, user):
    org = case.organisation.name
    if channel == MessageChannel.WHATSAPP:
        reminder_ready = reminder and not tw.template_waiting("TWILIO_WA_CONTENT_INTRO_REMINDER")
        content = (settings.TWILIO_WA_CONTENT_INTRO_REMINDER if reminder_ready else "") or settings.TWILIO_WA_CONTENT_INTRO
        return outbound.send(channel=channel, number=number, purpose=MessagePurpose.INTRODUCTION, wa_content=content.strip(),
                             wa_variables={1: org}, user=user, sample_case=case)
    name = "outreach_intro_reminder_sms" if reminder else "outreach_intro_sms"
    return outbound.send(channel=channel, number=number, purpose=MessagePurpose.INTRODUCTION, sms_body=wording(name, org),
                         user=user, sample_case=case)


def tried_this_number(target) -> bool:
    """True when this case or KII record was already asked on its current mobile and the introduction never arrived or
    got no answer after the reminder (2026-10-14). Such a number is not asked again -- on the first fresh-start day 51
    introductions went to numbers not on WhatsApp, and a second batch would have messaged them all again. A corrected
    number can be asked."""
    kii = hasattr(target, "kii_id")
    number = _kii_mobile(target) if kii else _mobile(target)[0]
    if not number:
        return False
    mine = Outreach.objects.filter(kii_record=target) if kii else Outreach.objects.filter(sample_case=target)
    return mine.filter(number_hash=number_hash(number), status__in=[OutreachStatus.NOT_DELIVERED, OutreachStatus.NO_REPLY]).exists()


def kii_introduction_candidates(groups=None, *, named_only: bool = False):
    """KII records never invited, in the chosen groups, with a number on file, no open link and no introduction yet."""
    from apps.kii.batch import GROUPS, candidates

    introduced = Outreach.objects.filter(kii_record=OuterRef("pk"), status__in=INTRODUCED)
    return candidates(("SMS", "WHATSAPP"), groups or GROUPS, named_only=named_only).exclude(Exists(introduced))


def _kii_mobile(record) -> str:
    from apps.kii.messages import kii_recipients

    return kii_recipients(record)["whatsapp_to"]


def _kii_addressee(record) -> str:
    """Who the introduction greets: the named informant with their organisation, or the organisation alone while no
    informant is named -- as the KII invitation does."""
    from apps.contacts.kii_finder import is_placeholder, organisation_name

    org = organisation_name(record)
    if is_placeholder(record):
        return org or "Sir/Madam"
    return f"{record.participant_name} ({org})" if org else record.participant_name


def _send_kii_intro(record, number: str, channel: str, *, reminder: bool, user):
    who = _kii_addressee(record)
    if channel == MessageChannel.WHATSAPP:
        reminder_ready = reminder and not tw.template_waiting("TWILIO_WA_CONTENT_KII_INTRO_REMINDER")
        content = (settings.TWILIO_WA_CONTENT_KII_INTRO_REMINDER if reminder_ready else "") or settings.TWILIO_WA_CONTENT_KII_INTRO
        name = "kii_outreach_intro_reminder_whatsapp" if reminder_ready else "kii_outreach_intro_whatsapp"
        return outbound.send(channel=channel, number=number, purpose=MessagePurpose.INTRODUCTION, wa_content=content.strip(),
                             wa_variables={1: who}, record_text=wording(name).replace("{{1}}", who), user=user,
                             kii_record=record)
    name = "kii_outreach_intro_reminder_sms" if reminder else "kii_outreach_intro_sms"
    return outbound.send(channel=channel, number=number, purpose=MessagePurpose.INTRODUCTION, sms_body=wording(name, who),
                         user=user, kii_record=record)


def send_kii_introduction(record, *, user) -> Outreach:
    """Introduce the study to one KII informant and ask whether they will take part (2026-10-14)."""
    channel = intro_channel(kii=True)
    if channel is None:
        raise OutreachError("not_configured",
                            "Introductions aren't set up yet: they need the study's WhatsApp number on Twilio (deploy/configure-twilio.sh).", 503)
    if not kii_introduction_candidates().filter(pk=record.pk).exists():
        raise OutreachError("not_ready", "This record can't be introduced: it must not be invited yet (Prospect), with a number "
                                         "on file, no open link and no earlier introduction.", 409)
    number = _kii_mobile(record)
    if not number:
        raise OutreachError("no_mobile", "No mobile number is on file (a landline can't receive WhatsApp or SMS).")
    if tried_this_number(record):
        raise OutreachError("already_tried", "This number was already asked and the message never arrived or got no answer. "
                                             "Phone them, or correct the number first.", 409)
    try:
        message = _send_kii_intro(record, number, channel, reminder=False, user=user)
    except outbound.OutboundError as exc:
        raise OutreachError(exc.code, str(exc), exc.status) from exc
    outreach = Outreach.objects.create(
        kii_record=record, channel=channel, number_hash=number_hash(number), number_masked=message.to_masked,
        intro_sent_at=timezone.now(), created_by=user,
    )
    log_action("outreach.introduced", record, {
        "kii_id": record.kii_id, "channel": channel, "recipient": message.to_masked, "outreach": outreach.pk,
        "user_id": getattr(user, "id", None),
    }, user=user)
    return outreach


def send_introduction(case, *, user) -> Outreach:
    """Introduce the study to one case and ask whether it will take part."""
    from apps.sampling.services import is_invitable

    channel = intro_channel()
    if channel is None:
        raise OutreachError("not_configured",
                            "Introductions aren't set up yet: they need the study's WhatsApp number on Twilio (deploy/configure-twilio.sh).", 503)
    if not is_invitable(case) or not introduction_candidates().filter(pk=case.pk).exists():
        raise OutreachError("not_ready", "This case can't be introduced: it must be verified (S03 or S04), with a number on file, "
                                         "no open invitation and no earlier introduction.", 409)
    number, respondent = _mobile(case)
    if not number:
        raise OutreachError("no_mobile", "No mobile number is on file (a landline can't receive WhatsApp or SMS).")
    if tried_this_number(case):
        raise OutreachError("already_tried", "This number was already asked and the message never arrived or got no answer. "
                                             "Phone them, or correct the number first.", 409)
    try:
        message = _send_intro(case, number, channel, reminder=False, user=user)
    except outbound.OutboundError as exc:
        raise OutreachError(exc.code, str(exc), exc.status) from exc
    outreach = Outreach.objects.create(
        sample_case=case, respondent=respondent, channel=channel, number_hash=number_hash(number),
        number_masked=message.to_masked, intro_sent_at=timezone.now(), created_by=user,
    )
    log_action("outreach.introduced", case, {
        "sample_id": case.sample_id, "channel": channel, "recipient": message.to_masked, "outreach": outreach.pk,
        "user_id": getattr(user, "id", None),
    }, user=user)
    return outreach


# --- Replies ------------------------------------------------------------------------------------------------------

def classify(body: str, button_payload: str = "") -> str:
    text = (button_payload or body or "").upper()
    words = " ".join(re.sub(r"[^\w\s]", " ", text).split())
    if words in {w.upper() for w in settings.OUTREACH_YES_WORDS}:
        return ReplyKind.YES
    if words in {w.upper() for w in settings.OUTREACH_NO_WORDS}:
        return ReplyKind.NO
    return ReplyKind.OTHER


def record_inbound(params: dict) -> tuple[InboundMessage | None, str]:
    """Stores one message from Twilio's incoming-message webhook. Returns (message, the sender's digits), or (None, "")
    for a message already stored -- Twilio retries when it gets no quick answer."""
    sid = params.get("MessageSid") or params.get("SmsSid") or ""
    if not sid or InboundMessage.objects.filter(provider_sid=sid).exists():
        return None, ""
    digits = "".join(ch for ch in params.get("From", "") if ch.isdigit())
    hashed = number_hash(digits)
    outreach = (Outreach.objects.filter(number_hash=hashed).select_related("sample_case", "kii_record")
                .order_by("-intro_sent_at").first())
    case, record = (outreach.sample_case, outreach.kii_record) if outreach else (None, None)
    if outreach is None:
        # Not an answer to an introduction, but it may still be someone on a case or KII record (2026-10-12): their
        # message then belongs in that conversation rather than among unknown numbers.
        from .matching import find_by_number

        case, record = find_by_number(digits)
    body = (params.get("Body") or "")[:2000]
    message = InboundMessage.objects.create(
        channel=MessageChannel.WHATSAPP, provider_sid=sid, outreach=outreach, sample_case=case, kii_record=record,
        number_hash=hashed, from_masked=tw.mask(digits), from_number="" if (case or record) else digits, body=body,
        kind=classify(body, params.get("ButtonPayload", "")),
    )
    return message, digits


def reply_window_open(hashed: str) -> bool:
    """WhatsApp allows a free-text message only within 24 hours of the person's own last message."""
    return InboundMessage.objects.filter(channel=MessageChannel.WHATSAPP, number_hash=hashed,
                                         received_at__gte=timezone.now() - timedelta(hours=24)).exists()


def _answered_today(message: InboundMessage) -> bool:
    return InboundMessage.objects.filter(
        channel=MessageChannel.WHATSAPP, number_hash=message.number_hash, received_at__gte=timezone.now() - timedelta(hours=24),
    ).exclude(pk=message.pk).exclude(auto_reply="").exists()


def _reply(message: InboundMessage, digits: str, text: str, *, purpose=MessagePurpose.REPLY, user=None, **links) -> bool:
    if not text:
        return False
    try:
        outbound.send(channel=MessageChannel.WHATSAPP, number=digits, purpose=purpose, wa_text=text, user=user,
                      sample_case=message.sample_case, kii_record=message.kii_record, **links)
    except outbound.OutboundError as exc:
        logger.warning("Reply to %s not sent: %s", message.from_masked, exc)
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        return False
    message.auto_reply = (message.auto_reply + "\n\n" + text).strip() if user is None else message.auto_reply
    message.save(update_fields=["auto_reply"])
    return True


def handle_inbound(message_id: int, digits: str) -> None:
    """Acts on one stored message (from a Celery task, so Twilio's webhook is answered at once)."""
    message = InboundMessage.objects.select_related("outreach__sample_case__organisation", "outreach__kii_record").get(pk=message_id)
    outreach = message.outreach
    if outreach is None:
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        if not _answered_today(message):
            _reply(message, digits, wording("outreach_unknown_number"))
        return
    if message.kind == ReplyKind.YES and outreach.status in ANSWERABLE:
        _accept(outreach, message, digits)
    elif message.kind == ReplyKind.YES and outreach.status == OutreachStatus.ACCEPTED:
        _reply(message, digits, wording("outreach_link_already_sent"))
    elif message.kind == ReplyKind.NO and outreach.status != OutreachStatus.DECLINED:
        _decline(outreach, message, digits)
    elif message.kind == ReplyKind.NO:
        return  # already recorded; no second acknowledgement
    else:
        # A question, another word, or a YES after saying no: a person decides.
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        if not _answered_today(message):
            _reply(message, digits, wording("outreach_auto_answer"))


def _ready_to_invite(case) -> bool:
    from apps.invitations.batch import OPEN_STATUSES
    from apps.invitations.models import InvitationToken
    from apps.sampling.services import is_contactable

    open_invitation = InvitationToken.objects.filter(sample_case=case, status__in=OPEN_STATUSES, expires_at__gt=timezone.now())
    return is_contactable(case) and not open_invitation.exists()


def _accept(outreach: Outreach, message: InboundMessage, digits: str) -> None:
    from apps.invitations.messages import build_messages, portal_base
    from apps.invitations.models import Channel
    from apps.invitations.services import TokenNotInvitable, issue_invitation

    if outreach.kii_record_id:
        return _accept_kii(outreach, message, digits)
    case = outreach.sample_case
    outreach.replied_at = timezone.now()
    if not _ready_to_invite(case):
        outreach.save(update_fields=["replied_at"])
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        _reply(message, digits, wording("outreach_link_unavailable"))
        log_action("outreach.accept_not_sent", case, {"sample_id": case.sample_id, "outreach": outreach.pk,
                                                      "workflow_status": case.workflow_status})
        return
    try:
        with transaction.atomic():
            raw_token, raw_code, token = issue_invitation(case, channel=Channel.WHATSAPP, issued_by=None)
            link = f"{portal_base(None)}/i/{raw_token}"
            text = build_messages(sample_case=case, link=link, manual_code=raw_code, expires_at=token.expires_at)["whatsapp"]
            outbound.send(channel=MessageChannel.WHATSAPP, number=digits, purpose=MessagePurpose.INVITATION, wa_text=text,
                          sample_case=case, invitation_token=token, redact_link=link, redact_code=raw_code)
            outreach.status, outreach.invitation_token = OutreachStatus.ACCEPTED, token
            outreach.save(update_fields=["status", "invitation_token", "replied_at"])
    except (outbound.OutboundError, TokenNotInvitable) as exc:
        # Nothing was kept: no link issued, the case still at S03/S04. A person follows up.
        outreach.save(update_fields=["replied_at"])
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        log_action("outreach.accept_not_sent", case, {"sample_id": case.sample_id, "outreach": outreach.pk, "error": str(exc)[:300]})
        return
    message.auto_reply = "(the invitation with the personal link and code)"
    message.save(update_fields=["auto_reply"])
    log_action("outreach.accepted", case, {"sample_id": case.sample_id, "outreach": outreach.pk, "invitation": token.pk})


def _decline(outreach: Outreach, message: InboundMessage, digits: str) -> None:
    """NO or STOP: the refusal is recorded as S12 Refused (PI decision, 2026-10-07) and any open invitation revoked.
    S12 never activates a Reserve by itself: that still needs its recorded reason and an authorising user."""
    from apps.invitations.models import InvitationToken, TokenStatus
    from apps.invitations.services import revoke_token
    from apps.sampling.models import WorkflowStatus
    from apps.sampling.services import WORKFLOW_TRANSITIONS, transition_workflow_status

    if outreach.kii_record_id:
        return _decline_kii(outreach, message, digits)
    case = outreach.sample_case
    for token in InvitationToken.objects.filter(sample_case=case).exclude(status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED,
                                                                                    TokenStatus.SUBMITTED, TokenStatus.QA_PASSED]):
        revoke_token(token, "Said no to the study's introduction")
    moved_to = ""
    if WorkflowStatus.S12_REFUSED in WORKFLOW_TRANSITIONS.get(case.workflow_status, set()):
        transition_workflow_status(case, WorkflowStatus.S12_REFUSED)
        moved_to = WorkflowStatus.S12_REFUSED
    outreach.status, outreach.replied_at = OutreachStatus.DECLINED, timezone.now()
    outreach.save(update_fields=["status", "replied_at"])
    _reply(message, digits, wording("outreach_declined_reply"))
    log_action("outreach.declined", case, {
        "sample_id": case.sample_id, "outreach": outreach.pk, "reply": message.body[:40], "moved_to": moved_to,
    })


def _kii_ready(record) -> bool:
    """A KII record a YES may still send a link to: not invited by hand meanwhile, declined or completed."""
    from apps.kii.batch import OPEN_STATUSES
    from apps.kii.models import KIIInvitationToken, KIIStatus

    open_link = KIIInvitationToken.objects.filter(kii_record=record, status__in=OPEN_STATUSES, expires_at__gt=timezone.now())
    return record.status in (KIIStatus.PROSPECT, KIIStatus.INVITED) and not open_link.exists()


def _accept_kii(outreach: Outreach, message: InboundMessage, digits: str) -> None:
    """YES from a KII informant: issue their self-service link (PROSPECT -> INVITED) and send it back in the chat, as
    one step -- if the message cannot be sent, no link is kept."""
    from apps.invitations.messages import portal_base
    from apps.invitations.models import Channel
    from apps.kii.messages import build_kii_messages
    from apps.kii.services import issue_kii_invitation

    record = outreach.kii_record
    outreach.replied_at = timezone.now()
    if not _kii_ready(record):
        outreach.save(update_fields=["replied_at"])
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        _reply(message, digits, wording("outreach_link_unavailable"))
        log_action("outreach.accept_not_sent", record, {"kii_id": record.kii_id, "outreach": outreach.pk, "status": record.status})
        return
    try:
        with transaction.atomic():
            raw_token, raw_code, token = issue_kii_invitation(record, channel=Channel.WHATSAPP, issued_by=None)
            link = f"{portal_base(None)}/ki/{raw_token}"
            text = build_kii_messages(kii_record=record, link=link, manual_code=raw_code, expires_at=token.expires_at)["whatsapp"]
            outbound.send(channel=MessageChannel.WHATSAPP, number=digits, purpose=MessagePurpose.INVITATION, wa_text=text,
                          kii_record=record, kii_invitation_token=token, redact_link=link, redact_code=raw_code)
            outreach.status, outreach.kii_invitation_token = OutreachStatus.ACCEPTED, token
            outreach.save(update_fields=["status", "kii_invitation_token", "replied_at"])
    except outbound.OutboundError as exc:
        # Nothing was kept: no link issued, the record still PROSPECT. A person follows up.
        outreach.save(update_fields=["replied_at"])
        message.needs_person = True
        message.save(update_fields=["needs_person"])
        log_action("outreach.accept_not_sent", record, {"kii_id": record.kii_id, "outreach": outreach.pk, "error": str(exc)[:300]})
        return
    message.auto_reply = "(the invitation with the personal link and code)"
    message.save(update_fields=["auto_reply"])
    log_action("outreach.accepted", record, {"kii_id": record.kii_id, "outreach": outreach.pk, "kii_invitation": token.pk})


def _decline_kii(outreach: Outreach, message: InboundMessage, digits: str) -> None:
    """NO or STOP from a KII informant: the record becomes DECLINED (as a decline on their own link does) and any open
    link is revoked, with one acknowledgement."""
    from apps.kii.batch import OPEN_STATUSES
    from apps.kii.models import KIIInvitationToken
    from apps.kii.services import SELF_SERVICE_DECLINED, advance_on_self_service, revoke_kii_invitation

    record = outreach.kii_record
    for token in KIIInvitationToken.objects.filter(kii_record=record, status__in=OPEN_STATUSES):
        revoke_kii_invitation(token, "Said no to the study's introduction")
    before = record.status
    advance_on_self_service(record, SELF_SERVICE_DECLINED)
    outreach.status, outreach.replied_at = OutreachStatus.DECLINED, timezone.now()
    outreach.save(update_fields=["status", "replied_at"])
    _reply(message, digits, wording("outreach_declined_reply"))
    log_action("outreach.declined", record, {
        "kii_id": record.kii_id, "outreach": outreach.pk, "reply": message.body[:40],
        "moved_to": record.status if record.status != before else "",
    })


def reply_from_inbox(message: InboundMessage, text: str, *, user) -> None:
    """A person answers in Conversations. The study's Twilio WhatsApp number is on no phone, so this is the only way
    to answer in the chat, and only inside WhatsApp's 24-hour window."""

    text = (text or "").strip()
    if not text:
        raise OutreachError("empty", "Write a reply first.")
    if not reply_window_open(message.number_hash):
        raise OutreachError("window_closed", "WhatsApp only allows a reply within 24 hours of their last message. Phone them instead.", 409)
    digits = message.from_number
    if not digits and message.outreach_id:
        target = message.outreach
        number = _kii_mobile(target.kii_record) if target.kii_record_id else _mobile(target.sample_case)[0]
        digits = number if number and number_hash(number) == message.number_hash else ""
    if not digits and (message.sample_case_id or message.kii_record_id):
        from .matching import number_matching

        digits = number_matching(message.number_hash, message.sample_case, message.kii_record)
    if not digits:
        raise OutreachError("no_number", "This number is no longer on file, so the portal can't reply. Phone them instead.", 409)
    try:
        sent = outbound.send(channel=MessageChannel.WHATSAPP, number=digits, purpose=MessagePurpose.REPLY, wa_text=text,
                             user=user, sample_case=message.sample_case, kii_record=message.kii_record)
    except outbound.OutboundError as exc:
        raise OutreachError(exc.code, str(exc), exc.status) from exc
    message.handled_by, message.handled_at, message.needs_person = user, timezone.now(), False
    message.save(update_fields=["handled_by", "handled_at", "needs_person"])
    log_action("conversation.replied", message.sample_case or message, {
        "message": message.pk, "recipient": sent.to_masked, "user_id": getattr(user, "id", None),
    }, user=user)


# --- No reply, and messages that never arrived ---------------------------------------------------------------------

def run_followups(now=None) -> dict:
    """The 08:00 run: one reminder OUTREACH_REMINDER_DAYS after an unanswered introduction, then, OUTREACH_GIVE_UP_DAYS
    later, the case is listed on Follow-ups for an RA to phone. Its status is not changed."""
    now = now or timezone.now()
    reminded = given_up = 0
    due = Outreach.objects.filter(status=OutreachStatus.INTRO_SENT,
                                  intro_sent_at__lte=now - timedelta(days=settings.OUTREACH_REMINDER_DAYS))
    for outreach in due.select_related("sample_case__organisation", "kii_record"):
        kii = outreach.kii_record_id is not None
        target = outreach.target
        channel = intro_channel(kii=kii)
        number = _kii_mobile(target) if kii else _mobile(target)[0]
        if not (_kii_ready(target) if kii else _ready_to_invite(target)) or channel is None or not number:
            continue
        if outreach.channel == MessageChannel.SMS or outreach.sms_fallback_sent:
            channel = MessageChannel.SMS if tw.sms_configured() else channel
        try:
            if kii:
                _send_kii_intro(target, number, channel, reminder=True, user=None)
            else:
                _send_intro(target, number, channel, reminder=True, user=None)
        except outbound.OutboundError as exc:
            if exc.code == "daily_limit_reached":
                break
            continue
        outreach.status, outreach.reminded_at = OutreachStatus.REMINDED, now
        outreach.save(update_fields=["status", "reminded_at"])
        ident = {"kii_id": target.kii_id} if kii else {"sample_id": target.sample_id}
        log_action("outreach.reminded", target, {**ident, "outreach": outreach.pk, "channel": channel})
        reminded += 1
    stale = Outreach.objects.filter(status=OutreachStatus.REMINDED,
                                    reminded_at__lte=now - timedelta(days=settings.OUTREACH_GIVE_UP_DAYS))
    for outreach in stale:
        outreach.status = OutreachStatus.NO_REPLY
        outreach.save(update_fields=["status"])
        given_up += 1
    return {"reminded": reminded, "no_reply": given_up}


def intro_not_delivered(message) -> None:
    """Twilio could not deliver an introduction (from outbound.record_status). A WhatsApp one is sent once by SMS, with
    the tap-to-reply link, where SMS is set up. Otherwise the introduction is marked not delivered and, when an email is
    on file, the invitation goes by email instead (email_after_failed_intro, in the background so Twilio's webhook is
    answered at once); with no email the case or record is listed for a person to phone."""
    if message.kii_record_id:
        mine = Outreach.objects.filter(kii_record=message.kii_record)
    elif message.sample_case_id:
        mine = Outreach.objects.filter(sample_case=message.sample_case)
    else:
        return
    outreach = mine.filter(status__in=OPEN_OUTREACH).order_by("-intro_sent_at").first()
    if outreach is None:
        return
    kii, target = outreach.kii_record_id is not None, outreach.target
    number = _kii_mobile(target) if kii else _mobile(target)[0]
    if message.channel == MessageChannel.WHATSAPP and not outreach.sms_fallback_sent and tw.sms_configured() and number:
        try:
            send = _send_kii_intro if kii else _send_intro
            send(target, number, MessageChannel.SMS, reminder=outreach.status == OutreachStatus.REMINDED, user=None)
        except outbound.OutboundError:
            pass
        else:
            outreach.sms_fallback_sent = True
            outreach.save(update_fields=["sms_fallback_sent"])
            ident = {"kii_id": target.kii_id} if kii else {"sample_id": target.sample_id}
            log_action("outreach.sms_fallback", target, {**ident, "outreach": outreach.pk})
            return
    outreach.status = OutreachStatus.NOT_DELIVERED
    outreach.save(update_fields=["status"])
    from .tasks import email_after_failed_intro_task

    email_after_failed_intro_task.delay(outreach.pk)


def email_after_failed_intro(outreach_id: int) -> str:
    """WhatsApp (and SMS, where set up) could not reach them, so the invitation goes by email when one is on file (PI
    decision, 2026-10-14: "WhatsApp first; without WhatsApp, email"). It is the ordinary invitation -- issued and sent
    as one step by the batch's send_one(), so a failed email keeps no link -- and the case moves to S05 (a KII record
    to INVITED), which takes it off the phone list. Inside the daily email limit; never for a case that was meanwhile
    invited, refused or completed. Returns what happened, for the audit log and tests."""
    from apps.invitations import batch as main_batch
    from apps.invitations.messages import portal_base

    outreach = Outreach.objects.select_related("sample_case", "kii_record").get(pk=outreach_id)
    if outreach.status != OutreachStatus.NOT_DELIVERED:
        return "not_failed"
    kii, target = outreach.kii_record_id is not None, outreach.target
    ident = {"kii_id": target.kii_id} if kii else {"sample_id": target.sample_id}
    if kii:
        from apps.kii import batch as kii_batch

        ready = _kii_ready(target) and bool(kii_batch.reachable_channels(target, ("EMAIL",)))
        send_one = kii_batch.send_one
    else:
        from apps.sampling.services import is_invitable

        ready = _ready_to_invite(target) and is_invitable(target) and bool(main_batch.reachable_channels(target, ("EMAIL",)))
        send_one = main_batch.send_one
    if not ready:
        return "no_email" if not (target.email if kii else main_batch.recipients(target)["email_to"]) else "not_ready"
    if main_batch.left_today() < 1:
        log_action("outreach.email_fallback_waiting", target, {**ident, "outreach": outreach.pk, "reason": "daily email limit reached"})
        return "daily_limit"
    try:
        sent = send_one(target, user=None, link_base=portal_base(None), channels=("EMAIL",))
    except Exception as exc:  # nothing was kept; the case stays on the phone list
        log_action("outreach.email_fallback_failed", target, {**ident, "outreach": outreach.pk, "error": str(exc)[:300]})
        return "failed"
    log_action("outreach.email_fallback", target, {**ident, "outreach": outreach.pk, "recipient": sent["sent_to"]})
    return "sent"


def unanswered(*, assigned_to=None) -> list[dict]:
    """Introductions with no answer after the reminder, or that never arrived, for cases still waiting: the Follow-ups
    list of organisations to phone."""
    items = Outreach.objects.filter(status__in=[OutreachStatus.NO_REPLY, OutreachStatus.NOT_DELIVERED],
                                    sample_case__workflow_status__in=["S03", "S04"]).select_related("sample_case__organisation")
    if assigned_to is not None:
        items = items.filter(sample_case__assigned_ra=assigned_to)
    return [{
        "sample_id": o.sample_case.sample_id, "organisation_name": o.sample_case.organisation.name,
        "status": o.status, "status_label": o.get_status_display(), "asked_on": timezone.localtime(o.intro_sent_at).date(),
        "number": o.number_masked,
    } for o in items.order_by("intro_sent_at")]


def kii_unanswered() -> list[dict]:
    """KII informants asked first who never answered after the reminder, or whose introduction never arrived, and who
    are still waiting (not invited by hand since): the KII Register's list of people to phone."""
    from apps.contacts.kii_finder import organisation_name

    items = (Outreach.objects.filter(status__in=[OutreachStatus.NO_REPLY, OutreachStatus.NOT_DELIVERED],
                                     kii_record__status="PROSPECT").select_related("kii_record").order_by("intro_sent_at"))
    return [{
        "kii_id": o.kii_record.kii_id, "kii_record_id": o.kii_record_id, "organisation": organisation_name(o.kii_record),
        "status": o.status, "status_label": o.get_status_display(), "asked_on": timezone.localtime(o.intro_sent_at).date(),
        "number": o.number_masked,
    } for o in items]
