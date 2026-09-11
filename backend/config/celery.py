"""
Celery app + Beat schedule.

The only two genuinely periodic background jobs this portal needs: the Kobo
reconciliation pull (docs/11_KOBOTOOLBOX_INTEGRATION.md -- the scheduled pull
is the source of truth, not the webhook) and reminder-queue dispatch
(docs/12_CONTACT_CRM_AND_MESSAGING.md). Do not add Celery tasks for anything
else without a matching justification -- see docs/04_TECH_STACK.md.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("drp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
