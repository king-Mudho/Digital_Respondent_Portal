"""Seeds the nightly renewal of the links on the Research Assistants' call lists (invitations.renewal, 8 Nov 2026), at
05:30 Harare time so every link works before the first call of the day. Same pattern as
messaging/migrations/0003_seed_dispatch_schedule.py; the PI can disable or move it in the Django admin."""

from django.db import migrations

NAME = "Renew call-list invitation links"


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    early, _ = CrontabSchedule.objects.get_or_create(
        minute="30", hour="5", day_of_week="*", day_of_month="*", month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name=NAME, defaults={"crontab": early, "task": "apps.invitations.tasks.renew_call_list_links_task", "enabled": True},
    )


def unseed(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [("invitations", "0006_invitationbatch_options"), ("django_celery_beat", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
