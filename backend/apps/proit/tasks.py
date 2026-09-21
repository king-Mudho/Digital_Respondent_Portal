"""AI desk research takes minutes (an AI searching the web and reading pages), longer than nginx keeps a
request open, so it runs in the Celery worker and the screen polls the run's status."""

from celery import shared_task

from .ai_research import run_research


@shared_task
def research_pre_profile(run_id: int) -> None:
    run_research(run_id)
