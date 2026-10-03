"""A batch sends one email after another with a short pause, longer than nginx keeps a request open, so it runs in
the Celery worker and the screen polls its progress."""

from celery import shared_task

from .batch import run_batch


@shared_task
def send_invitation_batch(batch_id: int) -> None:
    run_batch(batch_id)
