"""
Seeds the reconciliation Celery Beat schedule as django_celery_beat
PeriodicTask/CrontabSchedule rows -- DB-config-driven per AGENTS.md ground
rule 7, editable via Django admin without a redeploy, exactly as
docs/11_KOBOTOOLBOX_INTEGRATION.md requires ("configurable via environment/
Celery Beat schedule, not hardcoded").

Active-hours/overnight windows (06:00-22:00 vs 22:00-06:00) are an
engineering placeholder -- the doc specifies the *frequency* (15 min active,
60 min overnight) but not the exact fieldwork hours boundary. Adjust the two
CrontabSchedule rows via Django admin once the PI confirms actual fieldwork
hours.
"""

from django.db import migrations


def seed_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    active_hours, _ = CrontabSchedule.objects.get_or_create(
        minute="*/15", hour="6-21", day_of_week="*", day_of_month="*", month_of_year="*",
    )
    overnight, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="22-23,0-5", day_of_week="*", day_of_month="*", month_of_year="*",
    )

    PeriodicTask.objects.get_or_create(
        name="Kobo reconciliation (active hours)",
        defaults={
            "crontab": active_hours,
            "task": "apps.kobo.tasks.reconcile_kobo_submissions",
            "enabled": True,
        },
    )
    PeriodicTask.objects.get_or_create(
        name="Kobo reconciliation (overnight)",
        defaults={
            "crontab": overnight,
            "task": "apps.kobo.tasks.reconcile_kobo_submissions",
            "enabled": True,
        },
    )


def unseed_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=["Kobo reconciliation (active hours)", "Kobo reconciliation (overnight)"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("kobo", "0001_initial"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, unseed_schedule),
    ]
