"""Seeds a daily Celery Beat schedule for the reminder dispatch task --
config-driven per AGENTS.md ground rule 7, same pattern as
kobo/migrations/0002_seed_reconciliation_schedule.py."""

from django.db import migrations


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    daily, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="8", day_of_week="*", day_of_month="*", month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name="Reminder queue dispatch",
        defaults={"crontab": daily, "task": "apps.messaging.tasks.run_reminder_dispatch", "enabled": True},
    )


def unseed(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="Reminder queue dispatch").delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0002_seed_reminder_sequence"), ("django_celery_beat", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
