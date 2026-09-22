"""Seeds a daily Celery Beat schedule for the test/pilot-data smell check (apps/audit/services.py,
apps/audit/tasks.py:check_test_data_smells_task) as a django_celery_beat PeriodicTask/CrontabSchedule row --
DB-config-driven per AGENTS.md ground rule 7, editable via Django admin without a redeploy, same pattern as
apps/kobo/migrations/0002_seed_reconciliation_schedule.py.

Runs at 06:00 UTC (before the working day starts) so a report is waiting rather than arriving mid-fieldwork.
Adjust the hour via Django admin (Periodic tasks) if a different time suits the team better.
"""

from django.db import migrations


def seed_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    daily, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="6", day_of_week="*", day_of_month="*", month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name="Daily test-data smell check",
        defaults={
            "crontab": daily,
            "task": "apps.audit.tasks.check_test_data_smells_task",
            "enabled": True,
        },
    )


def unseed_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="Daily test-data smell check").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_performance_indexes"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, unseed_schedule),
    ]
