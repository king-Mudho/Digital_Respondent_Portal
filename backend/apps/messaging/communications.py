"""Communications: one place to message respondents and key informants and follow every message (2026-10-12).

A conversation is everything between the study and one Main-400 case or one KII record:

- messages the portal sent (ProviderMessage: WhatsApp, SMS, email) with what happened to each -- sent, delivered,
  read, not delivered -- and emails the team wrote in Gmail (apps/messaging/mailbox.py);
- messages received (InboundMessage: WhatsApp to the study's Twilio number, matched email replies);
- what happened around them: invitations issued, invitations sent by hand from the study phone (no delivery report),
  the link opened, consent, the questionnaire submitted, follow-ups marked sent, phone calls logged.

Who sees what is decided here, once, for the list, the thread and sending: the PI, Field Coordinator and Supervisor
(read-only) see everything; a Contact RA sees the Main-400 cases assigned to them; a KII RA sees KII records. Messages
from numbers the study has no record of go to the PI and Field Coordinator only.

Sending a message written here (send_message) refuses text a respondent must never see (AGENTS.md rule 2), a locked
Reserve (rule 4), a participant who withdrew, and WhatsApp free text outside the 24 hours WhatsApp allows after the
person's own last message.
"""

import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from apps.audit.utils import log_action

from . import outbound
from . import twilio_client as tw
from .hashing import email_hash, mask_email, number_hash
from .matching import contact_numbers
from .models import (
    InboundMessage,
    MailboxCursor,
    MessageChannel,
    MessageLog,
    MessageProvider,
    MessagePurpose,
    ProviderMessage,
    ProviderStatus,
    ReplyKind,
)

PAGE_SIZE = 30
NOT_DELIVERED = [ProviderStatus.UNDELIVERED, ProviderStatus.FAILED]
WRITE_ROLES = {"PI_ADMIN", "FIELD_COORDINATOR", "CONTACT_RA", "KII_RA"}
SEE_ALL_ROLES = {"PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"}

# Twilio's error codes in words a coordinator can act on.
DELIVERY_ERRORS = {
    "30003": "The phone was off or out of reach.",
    "30004": "The number is blocking messages from the study.",
    "30005": "The number does not exist or is no longer in use.",
    "30006": "That number is a landline or cannot receive SMS.",
    "30007": "The network filtered the message as unwanted.",
    "30008": "The network did not say why it was not delivered.",
    "63003": "This number is not on WhatsApp. Try SMS, email or a phone call.",
    "63016": "WhatsApp refused it: either the template is not approved yet, or a free-text message was sent more than "
             "24 hours after their last message.",
    "63024": "WhatsApp could not reach this number (not a WhatsApp account).",
    "63032": "The person has opted out of messages from businesses on WhatsApp.",
    "63049": "WhatsApp held back a marketing message to this person (Meta limits how many they receive).",
    "63051": "WhatsApp is pausing messages to this person for now.",
}


class CommunicationError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


# --- Who sees what -------------------------------------------------------------------------------------------------

def role_of(user) -> str:
    return getattr(getattr(user, "role", None), "name", "") or ""


def can_write(user) -> bool:
    return role_of(user) in WRITE_ROLES


def visible_cases(user):
    from apps.sampling.models import SampleCase

    role = role_of(user)
    cases = SampleCase.objects.select_related("organisation")
    if role in SEE_ALL_ROLES:
        return cases
    if role == "CONTACT_RA":
        return cases.filter(assigned_ra=user)
    return cases.none()


def visible_records(user):
    from apps.kii.models import KIIRecord

    if role_of(user) in SEE_ALL_ROLES | {"KII_RA"}:
        return KIIRecord.objects.all()
    return KIIRecord.objects.none()


def sees_unknown_senders(user) -> bool:
    return role_of(user) in SEE_ALL_ROLES


def get_subject(user, kind: str, pk):
    """The case or KII record, if this user may see its conversation; otherwise CommunicationError(404)."""
    queryset = visible_cases(user) if kind == "main" else visible_records(user) if kind == "kii" else None
    subject = queryset.filter(pk=pk).first() if queryset is not None and str(pk).isdigit() else None
    if subject is None:
        raise CommunicationError("not_found", "That conversation was not found, or is not one you can open.", 404)
    return subject


def _link(kind: str) -> str:
    return "sample_case" if kind == "main" else "kii_record"


# --- Wording helpers -----------------------------------------------------------------------------------------------

def delivery_problem(message: ProviderMessage) -> str:
    if message.status not in NOT_DELIVERED:
        return ""
    return DELIVERY_ERRORS.get(message.error_code) or message.error_message or "It was not delivered."


def split_quoted(text: str) -> tuple[str, str]:
    """(what they wrote, the earlier message their email quotes). The quote starts at "On ... wrote:", a line of
    "-----Original Message-----" / "From:" after a blank line, or the first run of ">" lines."""
    text = text or ""
    # Gmail wraps a long "On <date>, <name> <address> wrote:" over two or three lines, and it can end the email.
    patterns = [r"\n\s*On [^\n]{5,200}?(?:\n[^\n]{0,200}?){0,2}wrote:\s*(?:\n|$)", r"\n-{2,}\s*Original Message\s*-{2,}", r"\n\s*From:\s.+\n\s*(Sent|Date):\s",
                r"\n\s*_{10,}\s*\n", r"\n(?:>.*\n?){2,}"]
    cut = len(text)
    for pattern in patterns:
        found = re.search(pattern, text, flags=re.IGNORECASE)
        if found and found.start() < cut:
            cut = found.start()
    return text[:cut].strip(), text[cut:].strip()


def _blocked_phrase(text: str) -> str:
    for phrase in settings.COMMUNICATION_BLOCKED_PHRASES:
        phrase = phrase.strip()
        if phrase and re.search(r"(?<![\w])" + re.escape(phrase), text, flags=re.IGNORECASE):
            return phrase
    return ""


# --- The list ------------------------------------------------------------------------------------------------------

def _annotated(queryset, kind: str):
    """Cases or records with their last activity of any kind, whether someone's message waits, and whether the last
    message sent did not arrive."""
    from apps.contacts.models import ContactEvent
    from apps.invitations.models import InvitationToken
    from apps.kii.models import KIIInvitationToken

    link = _link(kind)
    sent = ProviderMessage.objects.filter(**{link: OuterRef("pk")}).order_by("-created_at")
    received = InboundMessage.objects.filter(**{link: OuterRef("pk")}).order_by("-received_at")
    if kind == "main":
        tokens = InvitationToken.objects.filter(sample_case=OuterRef("pk")).order_by("-issued_at")
    else:
        tokens = KIIInvitationToken.objects.filter(kii_record=OuterRef("pk")).order_by("-issued_at")
    latest = [Subquery(sent.values("created_at")[:1]), Subquery(received.values("received_at")[:1]),
              Subquery(tokens.values("issued_at")[:1])]
    if kind == "main":
        latest.append(Subquery(ContactEvent.objects.filter(sample_case=OuterRef("pk")).order_by("-occurred_at")
                               .values("occurred_at")[:1]))
        latest.append(Subquery(MessageLog.objects.filter(sample_case=OuterRef("pk")).exclude(sent_at=None)
                               .order_by("-sent_at").values("sent_at")[:1]))
    epoch = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)
    return queryset.annotate(
        last_activity=Greatest(*[Coalesce(expr, epoch) for expr in latest]),
        waiting=Exists(InboundMessage.objects.filter(**{link: OuterRef("pk")}, needs_person=True, handled_at=None)),
        last_sent_status=Subquery(sent.values("status")[:1]),
    ).filter(last_activity__gt=epoch)


def _search(queryset, kind: str, q: str):
    if not q:
        return queryset
    if kind == "main":
        return queryset.filter(Q(organisation__name__icontains=q) | Q(sample_id__icontains=q)
                               | Q(respondents__full_name__icontains=q)).distinct()
    return queryset.filter(Q(participant_name__icontains=q) | Q(kii_id__icontains=q)
                           | Q(metadata__organisation_name__icontains=q)).distinct()


def _channel_filter(queryset, kind: str, channel: str):
    if channel not in MessageChannel.values:
        return queryset
    link = _link(kind)
    return queryset.filter(Exists(ProviderMessage.objects.filter(**{link: OuterRef("pk")}, channel=channel))
                           | Exists(InboundMessage.objects.filter(**{link: OuterRef("pk")}, channel=channel)))


def _title(subject, kind: str) -> tuple[str, str, str]:
    """(organisation, person, reference)."""
    if kind == "main":
        people = sorted(subject.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))
        return subject.organisation.name, people[0].full_name if people else "", subject.sample_id
    from apps.contacts.kii_finder import organisation_name

    return organisation_name(subject) or subject.participant_name, subject.participant_name, subject.kii_id


def _last_message(subject, kind: str) -> dict:
    link = _link(kind)
    out = ProviderMessage.objects.filter(**{link: subject}).order_by("-created_at").first()
    inc = InboundMessage.objects.filter(**{link: subject}).order_by("-received_at").first()
    if inc and (out is None or inc.received_at >= out.created_at):
        body = split_quoted(inc.body)[0] if inc.channel == MessageChannel.EMAIL else inc.body
        return {"direction": "in", "channel": inc.channel, "text": (inc.subject + " — " if inc.subject else "") + body}
    if out:
        return {"direction": "out", "channel": out.channel, "text": (out.subject + " — " if out.subject else "") + out.body}
    return {"direction": "", "channel": "", "text": ""}


def _channels_used(subject, kind: str) -> list[str]:
    link = _link(kind)
    used = set(ProviderMessage.objects.filter(**{link: subject}).values_list("channel", flat=True))
    used |= set(InboundMessage.objects.filter(**{link: subject}).values_list("channel", flat=True))
    return [c for c in (MessageChannel.WHATSAPP, MessageChannel.SMS, MessageChannel.EMAIL) if c in used]


def thread_list(user, *, show: str = "all", register: str = "", channel: str = "", q: str = "", page: int = 1) -> dict:
    q = (q or "").strip()[:100]
    rows = []
    for kind, queryset in (("main", visible_cases(user)), ("kii", visible_records(user))):
        if register and register != kind:
            continue
        queryset = _channel_filter(_search(_annotated(queryset, kind), kind, q), kind, channel)
        if show == "waiting":
            queryset = queryset.filter(waiting=True)
        elif show == "failed":
            queryset = queryset.filter(last_sent_status__in=NOT_DELIVERED)
        rows += [(kind, s) for s in queryset.prefetch_related("respondents" if kind == "main" else "invitation_tokens")]
    # Waiting first, then the most recent activity; the id breaks ties so pages never overlap.
    rows.sort(key=lambda r: (r[1].waiting, r[1].last_activity, r[0] == "main", r[1].pk), reverse=True)
    total = len(rows)
    page = max(1, int(page or 1))
    results = []
    for kind, subject in rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
        organisation, person, ref = _title(subject, kind)
        results.append({
            "kind": kind, "id": subject.pk, "ref": ref, "organisation": organisation, "person": person,
            "last_activity": subject.last_activity, "waiting": subject.waiting,
            "last_sent_status": subject.last_sent_status or "", "channels": _channels_used(subject, kind),
            "last_message": _last_message(subject, kind),
        })
    unknown = InboundMessage.objects.filter(sample_case=None, kii_record=None, needs_person=True, handled_at=None).count() \
        if sees_unknown_senders(user) else 0
    return {"count": total, "page": page, "page_size": PAGE_SIZE, "results": results, "unknown_waiting": unknown}


# --- One conversation ----------------------------------------------------------------------------------------------

def _out_item(m: ProviderMessage) -> dict:
    # A copy found in the mailbox's sent folder: written in Gmail, or sent by the portal before 12 Oct 2026 without a
    # Message-ID it kept. Which one is not known, so it is not called "written in Gmail".
    from_mailbox = m.provider == MessageProvider.GMAIL_SENT
    return {
        "type": "out", "id": f"out-{m.pk}", "at": m.created_at, "channel": m.channel, "purpose": m.purpose,
        "purpose_label": "Email from the study mailbox" if from_mailbox else m.get_purpose_display(),
        "provider": m.provider, "status": m.status,
        "status_label": m.get_status_display(), "problem": delivery_problem(m), "subject": m.subject, "body": m.body,
        "to": m.to_masked, "by": m.sent_by.username if m.sent_by_id else ("" if from_mailbox else "automatic"),
        "from_mailbox": from_mailbox,
    }


# How close a sent-folder copy must be to an "invitation emailed" audit entry to be that invitation email.
MAILBOX_COPY_WINDOW = timedelta(minutes=15)


def _mailbox_copy(items: list[dict], sent_at):
    for item in items:
        if item["type"] == "out" and item["from_mailbox"] and abs(item["at"] - sent_at) <= MAILBOX_COPY_WINDOW:
            return item
    return None


def _in_item(m: InboundMessage) -> dict:
    text, quoted = split_quoted(m.body) if m.channel == MessageChannel.EMAIL else (m.body, "")
    return {
        "type": "in", "id": f"in-{m.pk}", "at": m.sent_at or m.received_at, "channel": m.channel, "from": m.from_masked,
        "subject": m.subject, "body": text, "quoted": quoted,
        "has_attachments": m.has_attachments and m.channel == MessageChannel.EMAIL,
        "attachments": [{
            "id": a.pk, "kind": a.kind, "label": a.get_kind_display(), "content_type": a.content_type,
            "contact": a.contact_text, "error": a.error, "size": a.size,
            "url": f"/communications/attachments/{a.pk}/" if a.file_ref else "",
        } for a in m.attachments.all()],
        "reply_kind": m.kind if m.channel == MessageChannel.WHATSAPP and m.kind != ReplyKind.OTHER else "",
        "waiting": m.needs_person and m.handled_at is None,
        "handled_by": m.handled_by.username if m.handled_by_id else "",
    }


def _event(at, text: str, *, tone: str = "info", detail: str = "") -> dict:
    return {"type": "event", "id": "", "at": at, "text": text, "detail": detail, "tone": tone}


CHANNEL_WORD = {"WHATSAPP": "WhatsApp", "EMAIL": "email", "SMS": "SMS", "PRINTED_CODE": "printed code", "QR": "QR code"}


def _token_events(tokens, emailed: dict, items: list[dict]) -> list[dict]:
    """`emailed` is {token id: when the invitation was emailed}, from the audit trail. When the email's copy came in
    from the mailbox's sent folder, that copy is labelled as the invitation and no second line is added for it."""
    events = []
    for token in tokens:
        channel = CHANNEL_WORD.get(token.channel, token.channel)
        events.append(_event(token.issued_at, f"Invitation link created ({channel}), expires "
                             f"{timezone.localtime(token.expires_at):%d %b %Y}"))
        if not token.provider_messages.exists():
            if token.pk in emailed:
                copy = _mailbox_copy(items, emailed[token.pk])
                if copy is not None:
                    copy["purpose_label"] = "Invitation (copy from the study mailbox)"
                else:
                    events.append(_event(emailed[token.pk], "Invitation emailed from the study address",
                                         detail="Sent before messages were kept in the portal, so its text is not shown here."))
            elif token.channel in ("WHATSAPP", "SMS"):
                events.append(_event(token.issued_at, f"Invitation sent by hand on {channel} from the study phone",
                                     tone="muted", detail="No delivery report: only messages the portal sends itself can "
                                                          "be followed to the phone."))
        reached = token.status not in ("GENERATED", "SENT", "EXPIRED", "REVOKED")
        if token.first_opened_at:
            events.append(_event(token.first_opened_at, "Opened the invitation link", tone="good"))
        elif reached:
            events.append(_event(token.issued_at, "Opened the invitation link", tone="good",
                                 detail="When is not known: opening times are kept from 13 October 2026."))
        if token.status == "REVOKED" and token.revoked_at:
            events.append(_event(token.revoked_at, "Invitation link cancelled", tone="muted", detail=token.revoked_reason))
        if token.status == "EXPIRED":
            events.append(_event(token.expires_at, "Invitation link expired", tone="muted"))
    return events


def _emailed(audit_model, action: str, object_type: str, tokens) -> dict:
    """{token id: when it was emailed} -- the first time, if it was emailed more than once."""
    out = {}
    rows = audit_model.objects.filter(action=action, object_type=object_type, object_id__in=[str(t.pk) for t in tokens])
    for object_id, created_at in rows.order_by("created_at").values_list("object_id", "created_at"):
        if str(object_id).isdigit():
            out.setdefault(int(object_id), created_at)
    return out


def thread(user, kind: str, pk) -> dict:
    from apps.audit.models import AuditEvent
    from apps.consent.models import ConsentRecord

    subject = get_subject(user, kind, pk)
    link = _link(kind)
    items = [_out_item(m) for m in ProviderMessage.objects.filter(**{link: subject}).select_related("sent_by")]
    items += [_in_item(m) for m in InboundMessage.objects.filter(**{link: subject}).select_related("handled_by").prefetch_related("attachments")]

    if kind == "main":
        from apps.contacts.models import ContactEvent
        from apps.kobo.models import QUANSubmission

        tokens = list(subject.invitation_tokens.all())
        items += _token_events(tokens, _emailed(AuditEvent, "invitation.emailed", "InvitationToken", tokens), items)
        for log in MessageLog.objects.filter(sample_case=subject).select_related("template", "triggered_by"):
            if getattr(log, "provider_message", None) is None and log.sent_at:
                step = log.template.name.replace("drp_", "").replace("_", " ")
                items.append(_event(log.sent_at, f"Follow-up ({step}) marked sent by hand on "
                                    f"{CHANNEL_WORD.get(log.channel, log.channel)}", tone="muted",
                                    detail=f"by {log.triggered_by.username}" if log.triggered_by_id else ""))
        for event in ContactEvent.objects.filter(sample_case=subject).select_related("ra"):
            items.append(_event(event.occurred_at, f"{event.get_channel_display()}: {event.get_outcome_display()}",
                                detail=" · ".join(x for x in (event.notes, f"by {event.ra.username}") if x)))
        for submission in QUANSubmission.objects.filter(sample_case=subject):
            items.append(_event(submission.submitted_at, "Questionnaire submitted", tone="good"))
        # Reserve replacement (2026-10-12): shown on both sides of the pair.
        reserve = subject.matched_case if subject.sample_type == "MAIN" else None
        if reserve is not None and reserve.status == "ACTIVATED" and reserve.activated_at:
            items.append(_event(reserve.activated_at, f"Replaced by Reserve {reserve.sample_id} "
                                f"({reserve.get_activation_reason_display()})", tone="muted",
                                detail=reserve.activation_evidence_note))
        if subject.sample_type == "RESERVE" and subject.activated_at:
            replaced = subject.matched_by.filter(sample_type="MAIN").first()
            items.append(_event(subject.activated_at, f"Reserve activated{f' to replace {replaced.sample_id}' if replaced else ''} "
                                f"({subject.get_activation_reason_display()})", detail=subject.activation_evidence_note))
    else:
        tokens = list(subject.invitation_tokens.all())
        items += _token_events(tokens, _emailed(AuditEvent, "kii_invitation.emailed", "KIIInvitationToken", tokens), items)

    for consent in ConsentRecord.objects.filter(**{link: subject}).order_by("timestamp"):
        tone = "good" if consent.decision == "GIVEN" else "warn"
        items.append(_event(consent.timestamp, f"Consent {consent.get_decision_display().lower()} "
                            f"({consent.get_consent_type_display().lower()})", tone=tone))

    items.sort(key=lambda i: (i["at"] or timezone.now(), 0 if i["type"] == "event" else 1))
    for n, item in enumerate(items):
        if item["type"] == "event":
            item["id"] = f"ev-{n}-{item['at']:%Y%m%d%H%M%S}"
    return {"subject": contact_card(subject, kind), "items": items, "composer": composer(user, subject, kind)}


def contact_card(subject, kind: str) -> dict:
    organisation, person, ref = _title(subject, kind)
    if kind == "main":
        people = [{"name": p.full_name, "role": p.get_role_category_display() if p.role_category else "",
                   "phone": p.phone, "whatsapp": p.whatsapp_number, "email": p.email, "eligible": p.is_eligible}
                  for p in sorted(subject.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))]
        return {"kind": kind, "id": subject.pk, "ref": ref, "organisation": organisation, "person": person,
                "status": subject.get_workflow_status_display() or "",
                "sample_type": subject.get_sample_type_display(), "province": subject.organisation.get_province_display(),
                "assigned_to": subject.assigned_ra.username if subject.assigned_ra_id else "",
                "page": f"/admin/sample/{subject.sample_id}", "people": people}
    return {"kind": kind, "id": subject.pk, "ref": ref, "organisation": organisation, "person": person,
            "status": subject.get_status_display(), "sample_type": "KII", "province": "",
            "assigned_to": "", "page": f"/admin/kii/{subject.pk}",
            "people": [{"name": subject.participant_name, "role": subject.participant_role, "phone": subject.phone,
                        "whatsapp": subject.whatsapp_number, "email": subject.email, "eligible": None}]}


# --- Sending -------------------------------------------------------------------------------------------------------

def _emails(subject, kind: str) -> list[str]:
    from apps.contacts.kii_finder import other_emails

    found = [p.email for p in subject.respondents.all()] if kind == "main" else [subject.email, *other_emails(subject)]
    return list(dict.fromkeys(e.strip() for e in found if e and "@" in e))


def _numbers(subject, kind: str) -> list[str]:
    return contact_numbers(case=subject if kind == "main" else None, record=subject if kind == "kii" else None)


def _withdrawn(subject) -> bool:
    from apps.consent.models import ConsentDecision, ConsentType
    from apps.consent.services import latest_consent

    record = latest_consent(subject, ConsentType.PARTICIPATION)
    return record is not None and record.decision == ConsentDecision.WITHDRAWN


def _blocked_reason(subject, kind: str) -> str:
    if kind == "main":
        from apps.sampling.services import is_invitable

        if not is_invitable(subject):
            return "This is a locked Reserve case: nobody is contacted until it is activated."
    if _withdrawn(subject):
        return "This participant withdrew from the study, so they are not contacted again."
    return ""


def composer(user, subject, kind: str) -> dict:
    blocked = _blocked_reason(subject, kind)
    numbers = _numbers(subject, kind)
    open_numbers = [n for n in numbers if _window_open(n)]
    emails = _emails(subject, kind)
    wa_ready = tw.credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip())
    last_email = InboundMessage.objects.filter(**{_link(kind): subject}, channel=MessageChannel.EMAIL).order_by("-received_at").first()

    whatsapp = {"available": False, "reason": "", "recipients": [{"value": n, "label": tw.mask(n)} for n in open_numbers]}
    if not wa_ready:
        whatsapp["reason"] = "WhatsApp sending isn't set up yet."
    elif not numbers:
        whatsapp["reason"] = "No mobile number is recorded."
    elif not open_numbers:
        whatsapp["reason"] = ("WhatsApp only allows a written message within 24 hours of their own last WhatsApp message. "
                              "Use an approved message below, email, or phone them.")
    else:
        whatsapp["available"] = True
    sms = {"available": tw.sms_configured() and bool(numbers), "recipients": [{"value": n, "label": tw.mask(n)} for n in numbers],
           "reason": "" if tw.sms_configured() else "SMS isn't set up (Zimbabwean numbers need a registered sender)."}
    if tw.sms_configured() and not numbers:
        sms["reason"] = "No mobile number is recorded."
    email = {"available": outbound.email_configured() and bool(emails), "recipients": [{"value": e, "label": e} for e in emails],
             "reason": "" if outbound.email_configured() else "Email isn't set up on the server.",
             "reply_subject": _reply_subject(last_email.subject) if last_email else "ABF-FST research study"}
    if outbound.email_configured() and not emails:
        email["reason"] = "No email address is recorded."
    actions = []
    if kind == "main" and not blocked:
        from .outreach import intro_channel

        if intro_channel() and numbers:
            actions.append({"key": "introduction", "label": "Send the introduction (ask first)"})
        actions.append({"key": "invitation", "label": "Send an invitation", "href": f"/admin/sample/{subject.sample_id}"})
    elif kind == "kii" and not blocked:
        actions.append({"key": "invitation", "label": "Send an invitation", "href": f"/admin/kii/{subject.pk}"})
    return {"can_write": can_write(user), "blocked": blocked, "whatsapp": whatsapp, "sms": sms, "email": email,
            "actions": actions, "max_length": settings.COMMUNICATION_MAX_LENGTH}


def _window_open(number: str) -> bool:
    from .outreach import reply_window_open

    return reply_window_open(number_hash(number))


def _reply_subject(subject: str) -> str:
    subject = (subject or "").strip()
    return subject if subject.lower().startswith("re:") else f"Re: {subject}" if subject else "ABF-FST research study"


def send_message(user, kind: str, pk, *, channel: str, recipient: str, text: str, subject_line: str = "") -> ProviderMessage:
    """A message written by a person in Communications, on one channel to one recorded number or address."""
    if not can_write(user):
        raise CommunicationError("forbidden", "Your role can read conversations but not send messages.", 403)
    subject = get_subject(user, kind, pk)
    text = (text or "").strip()
    if not text:
        raise CommunicationError("empty", "Write a message first.")
    if len(text) > settings.COMMUNICATION_MAX_LENGTH:
        raise CommunicationError("too_long", f"Keep it under {settings.COMMUNICATION_MAX_LENGTH} characters.")
    phrase = _blocked_phrase(text + " " + (subject_line or ""))
    if phrase:
        raise CommunicationError("blocked_phrase", f"Take out \"{phrase}\": the study never uses that word with participants. "
                                 "This is a research study, not a financing decision.")
    blocked = _blocked_reason(subject, kind)
    if blocked:
        raise CommunicationError("not_contactable", blocked, 409)
    links = {_link(kind): subject}
    recipient = (recipient or "").strip()
    try:
        if channel == MessageChannel.EMAIL:
            if recipient.lower() not in {e.lower() for e in _emails(subject, kind)}:
                raise CommunicationError("unknown_recipient", "Choose one of the addresses recorded for them.")
            last = (InboundMessage.objects.filter(**links, channel=MessageChannel.EMAIL, number_hash=email_hash(recipient))
                    .order_by("-received_at").first())
            sent = outbound.send_email(to=recipient, subject=(subject_line or "").strip()[:200] or "ABF-FST research study",
                                       body=text, purpose=MessagePurpose.MESSAGE, user=user,
                                       in_reply_to=last.provider_sid if last else "", **links)
            to_masked = mask_email(recipient)
        elif channel in (MessageChannel.WHATSAPP, MessageChannel.SMS):
            digits = "".join(ch for ch in recipient if ch.isdigit())
            if digits not in _numbers(subject, kind):
                raise CommunicationError("unknown_recipient", "Choose one of the numbers recorded for them.")
            if channel == MessageChannel.WHATSAPP and not _window_open(digits):
                raise CommunicationError("window_closed", "WhatsApp only allows a written message within 24 hours of their "
                                         "own last WhatsApp message. Use an approved message, email, or phone them.", 409)
            sent = outbound.send(channel=channel, number=digits, purpose=MessagePurpose.MESSAGE,
                                 wa_text=text if channel == MessageChannel.WHATSAPP else "",
                                 sms_body=text if channel == MessageChannel.SMS else "", user=user, **links)
            to_masked = tw.mask(digits)
        else:
            raise CommunicationError("bad_channel", "Choose WhatsApp, SMS or email.")
    except outbound.OutboundError as exc:
        raise CommunicationError(exc.code, str(exc), exc.status) from exc
    except CommunicationError:
        raise
    except Exception as exc:  # the mail server refused or timed out; send_email recorded it as failed
        raise CommunicationError("send_failed", f"The message was not sent: {exc}", 502) from exc
    mark_handled(user, kind, pk, _subject=subject)
    log_action("communication.sent", subject, {
        "channel": channel, "recipient": to_masked, "provider_message": sent.pk, "user_id": user.id,
        "ref": getattr(subject, "sample_id", None) or getattr(subject, "kii_id", None),
    }, user=user)
    return sent


def mark_handled(user, kind: str, pk, *, _subject=None) -> int:
    if not can_write(user):
        raise CommunicationError("forbidden", "Your role can read conversations but not change them.", 403)
    subject = _subject or get_subject(user, kind, pk)
    return InboundMessage.objects.filter(**{_link(kind): subject}, needs_person=True, handled_at=None).update(
        needs_person=False, handled_by=user, handled_at=timezone.now())


# --- Channel health ------------------------------------------------------------------------------------------------

def summary(user) -> dict:
    since = timezone.now() - timedelta(days=7)
    cases, records = visible_cases(user), visible_records(user)
    scoped = ProviderMessage.objects.filter(Q(sample_case__in=cases) | Q(kii_record__in=records), created_at__gte=since)
    week = {c: {s: 0 for s in ProviderStatus.values} for c in MessageChannel.values}
    for channel, status in scoped.values_list("channel", "status"):
        week[channel][status] += 1
    received = InboundMessage.objects.filter(Q(sample_case__in=cases) | Q(kii_record__in=records), received_at__gte=since)
    inbox = MailboxCursor.objects.filter(folder=settings.EMAIL_INBOX_FOLDER).first()
    approvals = tw.template_approvals()
    return {
        "whatsapp": {
            "configured": tw.credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip()),
            "sender": tw.mask(settings.TWILIO_WHATSAPP_FROM or ""), "left_today": outbound.left_today(MessageChannel.WHATSAPP),
            "daily_max": outbound.daily_max(MessageChannel.WHATSAPP), "templates": approvals,
            "templates_approved": sum(1 for t in approvals if t["status"] == "approved"),
        },
        "sms": {"configured": tw.sms_configured(), "left_today": outbound.left_today(MessageChannel.SMS),
                "daily_max": outbound.daily_max(MessageChannel.SMS)},
        "email": {"configured": outbound.email_configured(), "from": settings.DEFAULT_FROM_EMAIL,
                  "inbox_sync": {"configured": bool((settings.EMAIL_IMAP_HOST or "").strip()),
                                 "last_synced_at": inbox.last_synced_at if inbox else None,
                                 "last_error": inbox.last_error if inbox else ""}},
        "week": week,
        "received_week": {c: received.filter(channel=c).count() for c in MessageChannel.values},
        "waiting": InboundMessage.objects.filter(Q(sample_case__in=cases) | Q(kii_record__in=records), needs_person=True,
                                                 handled_at=None).count(),
    }


def unknown_senders(user) -> list[dict]:
    """Messages from numbers the study has no record of: PI and Field Coordinator only."""
    if not sees_unknown_senders(user):
        return []
    return [_in_item(m) | {"message_id": m.pk} for m in
            InboundMessage.objects.filter(sample_case=None, kii_record=None).prefetch_related("attachments").order_by("-received_at")[:100]]
