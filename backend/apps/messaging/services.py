"""
Reminder queue dispatch. Never sends uncontrolled messages -- only ever
dispatches from the approved Day 0/2/4-5/7 sequence
(docs/12_CONTACT_CRM_AND_MESSAGING.md); every other outbound message is an
explicit RA action recorded against them (MessageLog.triggered_by), never
this automated path.
"""

from django.utils import timezone

from apps.sampling.models import SampleCase, SampleType, WorkflowStatus
from apps.sampling.services import transition_workflow_status
from apps.invitations.models import InvitationToken

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


def _latest_token(sample_case: SampleCase) -> InvitationToken | None:
    return InvitationToken.objects.filter(sample_case=sample_case).order_by("-issued_at").first()


def _attempt_send(case: SampleCase, step: ReminderSequenceStep) -> MessageLog:
    log = MessageLog.objects.create(
        sample_case=case,
        template=step.template,
        channel=step.channel,
        status=MessageStatus.QUEUED,
        triggered_by=None,  # the approved automated sequence, per docs/05
    )

    respondent = case.respondents.first()
    phone = getattr(respondent, "whatsapp_number", "") or getattr(respondent, "phone", "") if respondent else ""

    try:
        if step.channel == MessageChannel.WHATSAPP and phone:
            WhatsAppClient().send_template_message(to_phone=phone, template_name=step.template.name)
            log.status = MessageStatus.SENT
            log.sent_at = timezone.now()
        else:
            # No phone on file yet, or a non-WhatsApp channel not
            # implemented by this client -- stays QUEUED for an RA to
            # action manually (e.g. an email fallback).
            pass
    except WhatsAppNotConfigured:
        # Expected until a real WhatsApp Business Platform account exists
        # (docs/27_AGENT_EXECUTION_PLAN.md open item) -- fails loudly into
        # the log rather than silently pretending to send.
        log.status = MessageStatus.FAILED

    log.save(update_fields=["status", "sent_at"])
    return log


def dispatch_due_reminders(reference_date=None) -> list[MessageLog]:
    """Run by Celery Beat (docs/04_TECH_STACK.md). For each MAIN case still
    awaiting a response, checks whether today matches a ReminderSequenceStep
    day_offset since the token was issued, and if that step hasn't already
    been sent for this case, dispatches it exactly once."""
    reference_date = (reference_date or timezone.now()).date()
    dispatched = []
    steps = list(ReminderSequenceStep.objects.select_related("template"))
    if not steps:
        return dispatched

    cases = SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status__in=AWAITING_RESPONSE_STATUSES)

    for case in cases:
        token = _latest_token(case)
        if not token:
            continue
        days_elapsed = (reference_date - token.issued_at.date()).days

        for step in steps:
            if step.day_offset != days_elapsed:
                continue
            already_sent = MessageLog.objects.filter(sample_case=case, template=step.template).exists()
            if already_sent:
                continue
            dispatched.append(_attempt_send(case, step))

    return dispatched


def exhaust_nonresponse_cases(reference_date=None) -> list[SampleCase]:
    """After the approved follow-up sequence is exhausted with no contact,
    a case becomes S13 (Nonresponse) and, from there, S16-eligible for
    reserve activation (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md,
    docs/12_CONTACT_CRM_AND_MESSAGING.md)."""
    reference_date = (reference_date or timezone.now()).date()
    final_step = ReminderSequenceStep.objects.order_by("-day_offset").first()
    if not final_step:
        return []

    transitioned = []
    cases = SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status__in=AWAITING_RESPONSE_STATUSES)
    for case in cases:
        token = _latest_token(case)
        if not token:
            continue
        days_elapsed = (reference_date - token.issued_at.date()).days
        if days_elapsed > final_step.day_offset:
            transition_workflow_status(case, WorkflowStatus.S13_NONRESPONSE)
            transitioned.append(case)
    return transitioned
