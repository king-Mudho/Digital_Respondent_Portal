from celery import shared_task

from .services import dispatch_due_reminders, exhaust_nonresponse_cases


@shared_task
def run_reminder_dispatch():
    from apps.sampling.replacement import run_auto_replacement

    from .outreach import run_followups

    dispatched = dispatch_due_reminders()
    exhausted = exhaust_nonresponse_cases()
    followups = run_followups()
    # Last, so a case that became Nonresponse or "no reply" this morning is replaced the same day (2026-10-12).
    replaced = run_auto_replacement()
    return {"dispatched": len(dispatched), "exhausted_to_nonresponse": len(exhausted), "introductions": followups,
            "replacement": replaced}


@shared_task
def handle_inbound_message(message_id: int, digits: str):
    """Acts on a WhatsApp message received by the study's Twilio number (outreach.handle_inbound). Run here so Twilio's
    webhook is answered at once: replying may wait on Twilio's retries."""
    from .outreach import handle_inbound

    handle_inbound(message_id, digits)


@shared_task
def sync_study_mailbox():
    """Copies replies from the study mailbox into Communications (apps/messaging/mailbox.py, 2026-10-12)."""
    from .mailbox import sync_mailbox

    return sync_mailbox()
