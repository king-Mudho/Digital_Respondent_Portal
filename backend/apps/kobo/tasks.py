"""
Celery Beat schedule for the Kobo reconciliation pull -- the actual source
of truth (docs/11_KOBOTOOLBOX_INTEGRATION.md), run every
KOBO_RECONCILIATION_INTERVAL_MINUTES. The webhook receiver (views.py) only
ever triggers an early run of this same task; it never writes
QUANSubmission rows itself.
"""

from celery import shared_task

from .models import ReconciliationTrigger
from .services import reconcile as reconcile_service


@shared_task
def reconcile_kobo_submissions(triggered_by: str = ReconciliationTrigger.SCHEDULE):
    log = reconcile_service(triggered_by=triggered_by)
    return log.pk
