"""
Celery Beat schedule for the Kobo reconciliation pull -- the actual source
of truth (docs/11_KOBOTOOLBOX_INTEGRATION.md), run every
KOBO_RECONCILIATION_INTERVAL_MINUTES. The webhook receiver (views.py) only
ever triggers an early run of this same task; it never writes
QUANSubmission rows itself.
"""

import logging

from celery import shared_task

from .models import ReconciliationTrigger
from .services import KoboNotConfigured
from .services import reconcile as reconcile_service

logger = logging.getLogger(__name__)


@shared_task
def reconcile_kobo_submissions(triggered_by: str = ReconciliationTrigger.SCHEDULE):
    try:
        log = reconcile_service(triggered_by=triggered_by)
    except KoboNotConfigured:
        # Expected until the production form is connected. Logged at DEBUG
        # so it does not fill the journal 96 times a day, and no
        # ReconciliationLog row is written for a run that never happened.
        logger.debug("Kobo reconciliation skipped: not configured.")
        return None
    return log.pk
