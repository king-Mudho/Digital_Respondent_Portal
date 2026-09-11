from celery import shared_task

from .services import dispatch_due_reminders, exhaust_nonresponse_cases


@shared_task
def run_reminder_dispatch():
    dispatched = dispatch_due_reminders()
    exhausted = exhaust_nonresponse_cases()
    return {"dispatched": len(dispatched), "exhausted_to_nonresponse": len(exhausted)}
