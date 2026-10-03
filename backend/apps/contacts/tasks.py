"""A contact search takes minutes (an AI searching the web), longer than nginx keeps a request open, so it runs in the
Celery worker and the screen polls the run's status."""

from celery import shared_task

from .contact_finder import run_search


@shared_task
def search_contacts(run_id: int) -> None:
    run_search(run_id)
