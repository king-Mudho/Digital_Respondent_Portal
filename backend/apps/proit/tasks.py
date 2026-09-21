"""AI desk research takes minutes (an AI searching the web and reading pages), longer than nginx keeps a
request open, so it runs in the Celery worker and the screen polls the run's status."""

from celery import shared_task

import logging

from .ai_research import run_research

logger = logging.getLogger(__name__)


@shared_task
def research_pre_profile(run_id: int) -> None:
    run_research(run_id)


@shared_task(bind=True, max_retries=5, default_retry_delay=300)
def push_profile_to_kobo(self, profile_id: int) -> None:
    """Sends a reconciled profile to KoboToolbox. Retries a few times so a brief Kobo outage never loses it."""
    from .kobo_submit import ProitKoboError, push_profile

    try:
        push_profile(profile_id)
    except ProitKoboError as exc:
        logger.warning("PROIT profile %s not sent to KoboToolbox: %s", profile_id, exc)
        raise self.retry(exc=exc)
