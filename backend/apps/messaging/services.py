"""
Reminder queue dispatch. Never sends uncontrolled messages -- only ever
dispatches from the approved Day 0/2/4-5/7 sequence
(docs/12_CONTACT_CRM_AND_MESSAGING.md); every other outbound message is an
explicit RA action recorded against them (MessageLog.triggered_by), never
this automated path.
"""

import re
from urllib.parse import quote

from django.utils import timezone

from apps.audit.utils import log_action
from apps.invitations.models import InvitationToken, TokenStatus
from apps.sampling.models import SampleCase, SampleType, WorkflowStatus
from apps.sampling.services import transition_workflow_status

from .models import MessageChannel, MessageLog, MessageStatus, ReminderSequenceStep
from .whatsapp_client import WhatsAppClient, WhatsAppNotConfigured

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

    __slots__ = ("case", "token", "respondent", "logs")

    def __init__(self, case, token, respondent, logs):
        self.case, self.token, self.respondent, self.logs = case, token, respondent, logs

    def delivered(self, step: ReminderSequenceStep) -> bool:
        return any(
            template_id == step.template_id and created_at >= self.token.issued_at
            for template_id, created_at in self.logs
        )

    @property
    def phone(self) -> str:
        return (self.respondent.whatsapp_number or self.respondent.phone) if self.respondent else ""


def _awaiting(assigned_to=None) -> list[_Awaiting]:
    cases = (
        SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status__in=AWAITING_RESPONSE_STATUSES)
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

    out = []
    for case in cases:
        token = tokens.get(case.id)
        if token is None:
            continue
        people = sorted(case.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))
        out.append(_Awaiting(case, token, people[0] if people else None, logs.get(case.id, [])))
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


def dispatch_due_reminders(reference_date=None) -> list[MessageLog]:
    """Run daily by Celery Beat. Sends the due reminder through the WhatsApp
    Business Platform when that is connected.

    When it is not, sends nothing and writes nothing: the reminder stays on
    the Follow-ups screen for an RA to send by hand. Previously every due
    reminder was written as a FAILED MessageLog -- shown on no screen, so no
    reminder was ever actually sent -- and a missed day (the check was an
    exact day match) meant that reminder was skipped for good.
    """
    reference_date = reference_date or timezone.localdate()
    dispatched = []
    steps = list(ReminderSequenceStep.objects.select_related("template"))
    if not steps:
        return dispatched
    client = WhatsAppClient()

    for item in _awaiting():
        step = _due_step(item, steps, reference_date)
        if step is None or step.channel != MessageChannel.WHATSAPP or not item.phone:
            continue
        try:
            client.send_template_message(to_phone=item.phone, template_name=step.template.name)
        except WhatsAppNotConfigured:
            return dispatched  # nothing can be sent automatically; the Follow-ups screen lists them
        dispatched.append(MessageLog.objects.create(
            sample_case=item.case, template=step.template, channel=step.channel,
            status=MessageStatus.SENT, sent_at=timezone.now(), triggered_by=None,
        ))
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
    """Digits for a wa.me link. Zimbabwean local numbers (07x...) get the
    263 country code; anything already international is kept."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "263" + digits[1:]
    return digits


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
            "whatsapp_link": whatsapp_link(item.phone, step.template.body),
        })
    items.sort(key=lambda entry: entry["invited_on"])
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
