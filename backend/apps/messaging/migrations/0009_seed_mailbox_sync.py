"""Seeds the Celery Beat schedule that reads the study mailbox (apps/messaging/mailbox.py, 2026-10-12), every
EMAIL_INBOX_POLL_MINUTES -- the interval can be changed later in Django admin (Periodic tasks) without a redeploy.
The task does nothing while EMAIL_IMAP_HOST is blank."""

from django.conf import settings
from django.db import migrations

NAME = "Study mailbox sync"


def seed(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    every, _ = IntervalSchedule.objects.get_or_create(every=max(1, settings.EMAIL_INBOX_POLL_MINUTES), period="minutes")
    PeriodicTask.objects.get_or_create(
        name=NAME, defaults={"interval": every, "task": "apps.messaging.tasks.sync_study_mailbox", "enabled": True},
    )


def unseed(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0008_communications"), ("django_celery_beat", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
