"""Seeds the Celery Beat schedule that rechecks with Twilio any SMS/WhatsApp still showing Queued or Sent
(outbound.recheck_statuses, 25 Nov 2026), every 15 minutes -- the interval can be changed later in Django admin
(Periodic tasks) without a redeploy. The task does nothing while Twilio is not set up."""

from django.db import migrations

NAME = "Twilio delivery status recheck"


def seed(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    every, _ = IntervalSchedule.objects.get_or_create(every=15, period="minutes")
    PeriodicTask.objects.get_or_create(
        name=NAME, defaults={"interval": every, "task": "apps.messaging.tasks.recheck_twilio_statuses", "enabled": True},
    )


def unseed(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0025_study_brief_wording"), ("django_celery_beat", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
