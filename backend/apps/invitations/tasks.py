"""A batch sends one email after another with a short pause, longer than nginx keeps a request open, so it runs in
the Celery worker and the screen polls its progress."""

from celery import shared_task

from .batch import run_batch


@shared_task
def send_invitation_batch(batch_id: int) -> None:
    run_batch(batch_id)


@shared_task
def renew_call_list_links_task() -> dict:
    """Nightly: renew the links on the Research Assistants' call lists before they run out (invitations.renewal)."""
    from django.conf import settings

    from .renewal import renew_call_list_links

    if not getattr(settings, "INVITATION_AUTO_RENEW", True):
        return {"skipped": "INVITATION_AUTO_RENEW is off"}
    result = renew_call_list_links(apply=True)
    return {"renewed": len(result["renewed"]), "left": len(result["skipped"])}
