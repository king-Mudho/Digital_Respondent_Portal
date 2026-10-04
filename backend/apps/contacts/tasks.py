"""A contact search takes minutes (an AI searching the web), longer than nginx keeps a request open, so it runs in the
background and the screen polls the run's status.

Searches have their own queue, RESEARCH_QUEUE (settings.CELERY_TASK_ROUTES), served by the drp-celery-research
worker. Before 2026-10-04 they shared the one worker with the KoboToolbox sync, AI drafts and email batches, so a batch
of 50 searches (about a minute each) held all of those up for nearly an hour."""

from celery import shared_task

from .contact_finder import run_search

RESEARCH_QUEUE = "research"


@shared_task(bind=True)
def search_contacts(self, run_id: int) -> None:
    # A search queued before the research lane existed sits in the default queue. Hand it over rather than run it
    # here, so the default worker is free again within seconds of the deploy.
    queue = (self.request.delivery_info or {}).get("routing_key")
    if queue and queue != RESEARCH_QUEUE:
        self.apply_async(args=[run_id], queue=RESEARCH_QUEUE)
        return
    run_search(run_id)
