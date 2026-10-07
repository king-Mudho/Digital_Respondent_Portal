"""
Reminder queue dispatch. Never sends uncontrolled messages -- only ever
dispatches from the approved Day 2 / Day 7 sequence
(docs/12_CONTACT_CRM_AND_MESSAGING.md); every other outbound message is an
explicit RA action recorded against them (MessageLog.triggered_by), never
this automated path. Automatic sending goes through Twilio (outbound.py) once
SMS or WhatsApp is set up; until then every due reminder waits on Follow-ups.
"""

from urllib.parse import quote

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.audit.utils import log_action
from apps.contacts.contact_text import first_mobile, foreign_number_digits
from apps.invitations.models import InvitationToken, TokenStatus
from apps.sampling.models import SampleCase, SampleType, WorkflowStatus
from apps.sampling.services import transition_workflow_status

from . import outbound
from . import twilio_client as tw
from .models import (
    MessageChannel,
    MessageLog,
    MessagePurpose,
    MessageStatus,
    MessageTemplate,
    ReminderSequenceStep,
)

# Workflow statuses where a reminder still makes sense -- once a case has
# moved past invitation (started/submitted/refused/etc.) the reminder
# sequence for *invitation follow-up* no longer applies.
AWAITING_RESPONSE_STATUSES = [
    WorkflowStatus.S04_INVITATION_PREPARED,
    WorkflowStatus.S05_INVITATION_SENT,
    WorkflowStatus.S06_INVITATION_OPENED,
]

DELIVERED_STATUSES = [MessageStatus.SENT, MessageStatus.DELIVERED]


def _latest_token(sample_case: SampleCase) -> InvitationToken | None:
    """The invitation the reminders are about: the case's live one. A
    superseded (EXPIRED) or REVOKED invitation never starts the clock."""
    return (
        InvitationToken.objects.filter(sample_case=sample_case)
        .exclude(status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED])
        .order_by("-issued_at")
        .first()
    )


class _Awaiting:
    """One awaiting case with everything the reminder rules need, loaded in
    bulk. The first version asked the database for each case's token,
    respondent and message logs separately -- several queries per invited
    case, which at 400 invitations meant well over a thousand per load of
    the Follow-ups screen."""

    __slots__ = ("case", "token", "respondent", "logs", "auto_failures")

    def __init__(self, case, token, respondent, logs, auto_failures=()):
        self.case, self.token, self.respondent, self.logs = case, token, respondent, logs
        self.auto_failures = auto_failures

    def auto_failed(self, step: ReminderSequenceStep) -> bool:
        """The automatic send of this reminder, for this invitation, did not reach the respondent. It is left for a
        person on Follow-ups and never tried again automatically: re-sending every morning would repeat the cost and
        the message."""
        return self.token is not None and any(
            template_id == step.template_id and created_at >= self.token.issued_at
            for template_id, created_at in self.auto_failures
        )

    @property
    def expired(self) -> bool:
        """The link no longer works. Tokens are only marked EXPIRED when someone tries one, so an unopened link past
        its date still reads SENT: the date decides."""
        return self.token is None or self.token.expires_at <= timezone.now()

    def delivered(self, step: ReminderSequenceStep) -> bool:
        return any(
            template_id == step.template_id and created_at >= self.token.issued_at
            for template_id, created_at in self.logs
        )

    @property
    def phone(self) -> str:
        return (self.respondent.whatsapp_number or self.respondent.phone) if self.respondent else ""

    @property
    def whatsapp_to(self) -> str:
        if not self.respondent:
            return ""
        return whatsapp_digits(self.respondent.whatsapp_number) or whatsapp_digits(self.respondent.phone)


def _awaiting(assigned_to=None, *, include_dead=False) -> list[_Awaiting]:
    """Invited cases still waiting for a response -- what the reminders, the Follow-ups screen and the Nonresponse
    rule all work from. A case whose respondent has asked for a call (an appointment REQUESTED or CONFIRMED) is not
    waiting: it is left out until the appointment is completed, missed or cancelled. Until 2026-10-06 it was not, so
    a respondent who had consented and booked a call was sent "please use the link you were sent", and once both
    reminders were marked sent the case could become Nonresponse and its Reserve be activated in its place.

    A case with no live invitation at all (every one revoked or superseded) is left out unless `include_dead`."""
    from apps.contacts.models import Appointment, AppointmentStatus

    open_appointment = Appointment.objects.filter(
        sample_case=OuterRef("pk"), status__in=[AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED],
    )
    cases = (
        SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status__in=AWAITING_RESPONSE_STATUSES)
        .exclude(Exists(open_appointment))
        .select_related("organisation")
        .prefetch_related("respondents")
    )
    if assigned_to is not None:
        cases = cases.filter(assigned_ra=assigned_to)
    cases = list(cases)
    ids = [case.id for case in cases]

    tokens: dict[int, InvitationToken] = {}
    live = (
        InvitationToken.objects.filter(sample_case_id__in=ids)
        .exclude(status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED])
        .order_by("-issued_at")
    )
    for token in live:
        tokens.setdefault(token.sample_case_id, token)

    logs: dict[int, list] = {}
    delivered = MessageLog.objects.filter(sample_case_id__in=ids, status__in=DELIVERED_STATUSES)
    for case_id, template_id, created_at in delivered.values_list("sample_case_id", "template_id", "created_at"):
        logs.setdefault(case_id, []).append((template_id, created_at))
    failures: dict[int, list] = {}
    failed = MessageLog.objects.filter(sample_case_id__in=ids, status=MessageStatus.FAILED, triggered_by__isnull=True)
    for case_id, template_id, created_at in failed.values_list("sample_case_id", "template_id", "created_at"):
        failures.setdefault(case_id, []).append((template_id, created_at))

    out = []
    for case in cases:
        token = tokens.get(case.id)
        if token is None and not include_dead:
            continue
        people = sorted(case.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))
        out.append(_Awaiting(case, token, people[0] if people else None, logs.get(case.id, []), failures.get(case.id, [])))
    return out


def _due_step(item: _Awaiting, steps, reference_date) -> ReminderSequenceStep | None:
    """The latest reminder step that is due and not yet delivered for this
    invitation. Only the latest: on day 8 an undelivered Day 2 reminder is
    superseded by the Day 7 one, never sent as a second message."""
    days_elapsed = (reference_date - timezone.localtime(item.token.issued_at).date()).days
    due = [step for step in steps if step.day_offset <= days_elapsed]
    if not due:
        return None
    return None if item.delivered(due[-1]) else due[-1]


def sms_reminder_text(template: MessageTemplate) -> str:
    """The SMS version of a reminder: the template "<name>_sms" when there is one (two-way SMS is not available in
    Zimbabwe, so the WhatsApp wording's "reply here" would not work by SMS), else the reminder's own wording."""
    sms = MessageTemplate.objects.filter(name=f"{template.name}_sms").first()
    return sms.body if sms else template.body


def automatic_channel(template_name: str) -> str | None:
    """How a reminder would go out automatically today: WhatsApp when its approved template is set up, else SMS, else
    not at all (it waits on Follow-ups)."""
    if tw.whatsapp_reminder_template(template_name):
        return MessageChannel.WHATSAPP
    return MessageChannel.SMS if tw.sms_configured() else None


def dispatch_due_reminders(reference_date=None) -> list[MessageLog]:
    """Run daily by Celery Beat. Sends each due reminder through Twilio (outbound.py): WhatsApp when its approved
    template is set up, otherwise SMS, to the respondent's mobile only.

    When neither is set up it sends nothing and writes nothing: the reminder stays on the Follow-ups screen for an RA
    to send by hand. (Before 2026-09-14 every due reminder was written as a FAILED MessageLog shown on no screen, and a
    missed day meant that reminder was skipped for good.) A send Twilio refuses is recorded FAILED and left for a
    person; it is never retried automatically. Until 2026-10-07 this was written against the Meta Cloud API, for which
    no account was ever provisioned, so no reminder was ever sent automatically.
    """
    reference_date = reference_date or timezone.localdate()
    dispatched = []
    steps = list(ReminderSequenceStep.objects.select_related("template"))
    if not steps or not any(automatic_channel(step.template.name) for step in steps):
        return dispatched  # nothing can be sent automatically; the Follow-ups screen lists them

    for item in _awaiting():
        if item.expired:
            continue  # a reminder about a link that no longer works; listed under expired_invitations()
        step = _due_step(item, steps, reference_date)
        to_phone = item.whatsapp_to  # a mobile, never a landline
        if step is None or not to_phone or item.auto_failed(step):
            continue
        channel = automatic_channel(step.template.name)
        if channel is None or outbound.left_today(channel) < 1:
            continue
        try:
            message = outbound.send(
                channel=channel, number=to_phone, purpose=MessagePurpose.REMINDER,
                sms_body=sms_reminder_text(step.template), wa_content=tw.whatsapp_reminder_template(step.template.name),
                user=None, sample_case=item.case,
            )
        except outbound.OutboundError as exc:
            if exc.code == "daily_limit_reached":
                continue
            MessageLog.objects.create(sample_case=item.case, template=step.template, channel=channel,
                                      status=MessageStatus.FAILED, triggered_by=None)
            log_action("reminder.automatic_failed", item.case, {
                "sample_id": item.case.sample_id, "template": step.template.name, "channel": channel, "error": str(exc)[:300],
            })
            continue
        log = MessageLog.objects.create(sample_case=item.case, template=step.template, channel=channel,
                                        status=MessageStatus.SENT, sent_at=timezone.now(), triggered_by=None)
        message.message_log = log
        message.save(update_fields=["message_log", "updated_at"])
        log_action("reminder.sent_automatically", item.case, {
            "sample_id": item.case.sample_id, "template": step.template.name, "channel": channel,
            "recipient": message.to_masked, "provider_message": message.pk,
        })
        dispatched.append(log)
    return dispatched


def exhaust_nonresponse_cases(reference_date=None) -> list[SampleCase]:
    """After the approved follow-up sequence is exhausted with no response,
    a case becomes S13 (Nonresponse) and, from there, S16-eligible for
    reserve activation (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md,
    docs/12_CONTACT_CRM_AND_MESSAGING.md).

    "Exhausted" means every reminder in the sequence was actually sent for
    the current invitation. Until 2026-09-14 the calendar alone decided: a
    case whose reminders had all failed to send (every case, with no
    WhatsApp account) became Nonresponse on day 8 and could be replaced by
    a reserve without anyone having followed up at all.
    """
    reference_date = reference_date or timezone.localdate()
    steps = list(ReminderSequenceStep.objects.select_related("template"))
    if not steps:
        return []
    final_offset = steps[-1].day_offset

    transitioned = []
    for item in _awaiting():
        days_elapsed = (reference_date - timezone.localtime(item.token.issued_at).date()).days
        if days_elapsed > final_offset and all(item.delivered(step) for step in steps):
            transition_workflow_status(item.case, WorkflowStatus.S13_NONRESPONSE)
            transitioned.append(item.case)
    return transitioned


# --- Follow-ups sent by hand (WhatsApp click-to-chat) ----------------------

def whatsapp_digits(phone: str) -> str:
    """Digits for a wa.me link or an SMS: the first mobile in the field, with its country code. A field holding
    several numbers ("0772 686106; 0773 626999") gives the first mobile -- joining every digit made a number that
    opened nobody.

    A landline gives "" -- WhatsApp and SMS cannot reach one. Until 2026-10-06 a field holding only a landline
    ("+263 9 75315", "0242 700000") still produced a link: the RA got a WhatsApp chat that could never be delivered,
    and the case read as invited. 17 registered respondents had only a landline. They are phoned instead."""
    mobile = first_mobile(phone)
    return mobile.lstrip("+") if mobile else foreign_number_digits(phone)


def whatsapp_link(phone: str, text: str) -> str:
    digits = whatsapp_digits(phone)
    return f"https://wa.me/{digits}?text={quote(text)}" if digits else f"https://wa.me/?text={quote(text)}"


def due_follow_ups(reference_date=None, *, assigned_to=None) -> list[dict]:
    """Every awaiting case with a reminder due and not yet sent, oldest
    invitation first -- the Follow-ups screen. `assigned_to` limits it to one
    Contact RA's assigned cases, like every other Contact RA list."""
    reference_date = reference_date or timezone.localdate()
    steps = list(ReminderSequenceStep.objects.select_related("template"))
    if not steps:
        return []
    items = []
    for item in _awaiting(assigned_to):
        if item.expired:
            continue  # the link has run out: re-invite rather than remind (expired_invitations)
        step = _due_step(item, steps, reference_date)
        if step is None:
            continue
        items.append({
            "sample_id": item.case.sample_id,
            "organisation_name": item.case.organisation.name,
            "workflow_status": item.case.workflow_status,
            "invited_on": timezone.localtime(item.token.issued_at).date(),
            "step_day": step.day_offset,
            "step_label": step.label or f"Day {step.day_offset} reminder",
            "template": step.template.name,
            "message": step.template.body,
            "respondent_name": item.respondent.full_name if item.respondent else "",
            "phone": item.phone,
            "can_whatsapp": bool(item.whatsapp_to),
            "whatsapp_link": whatsapp_link(item.whatsapp_to, step.template.body),
            # Twilio will send it at the next morning run; or it tried and the message did not get through.
            "auto_failed": item.auto_failed(step),
            "sends_automatically": bool(item.whatsapp_to) and not item.auto_failed(step)
                                   and automatic_channel(step.template.name) is not None,
            "expires_on": timezone.localtime(item.token.expires_at).date(),
        })
    items.sort(key=lambda entry: entry["invited_on"])
    return items


def expired_invitations(*, assigned_to=None) -> list[dict]:
    """Invited cases still waiting for a response whose link no longer works: it ran past its expiry date, or every
    invitation was revoked or superseded with none issued since. Neither a reminder nor the Nonresponse rule can help
    them -- a reminder points at a dead link, and Nonresponse needs every reminder sent. Until 2026-10-06 they were
    listed nowhere: an expired case kept getting reminders, and one with no live invitation simply dropped out of the
    Follow-ups screen while still reading "Invitation sent". The answer is a new invitation from the case page."""
    items = []
    for item in _awaiting(assigned_to, include_dead=True):
        if not item.expired:
            continue
        if item.token is None and item.case.workflow_status == WorkflowStatus.S04_INVITATION_PREPARED:
            continue  # prepared but never sent: nothing has run out
        items.append({
            "sample_id": item.case.sample_id,
            "organisation_name": item.case.organisation.name,
            "workflow_status": item.case.workflow_status,
            "invited_on": timezone.localtime(item.token.issued_at).date() if item.token else None,
            "expired_on": timezone.localtime(item.token.expires_at).date() if item.token else None,
            "reason": "expired" if item.token else "no_live_invitation",
            "respondent_name": item.respondent.full_name if item.respondent else "",
            "phone": item.phone,
        })
    items.sort(key=lambda entry: (entry["expired_on"] is not None, entry["expired_on"] or entry["sample_id"]))
    return items


def record_manual_follow_up(*, sample_case: SampleCase, template_name: str, user) -> MessageLog:
    """An RA sent a due reminder by hand. Recorded as SENT against that RA
    (MessageLog.triggered_by, docs/12 messaging governance) and audited, so
    it counts toward the sequence exactly like an automated send."""
    step = ReminderSequenceStep.objects.select_related("template").get(template__name=template_name)
    log = MessageLog.objects.create(
        sample_case=sample_case, template=step.template, channel=step.channel,
        status=MessageStatus.SENT, sent_at=timezone.now(), triggered_by=user,
    )
    log_action("messaging.follow_up_sent", log, {
        "sample_id": sample_case.sample_id, "template": template_name, "manual": True,
    })
    return log
