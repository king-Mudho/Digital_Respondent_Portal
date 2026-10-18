"""Thanking participants who completed (PI, 18 Oct 2026; apps/messaging/thanks.py): the new message purpose and reply
kind, the portal's copy of the WhatsApp thank-you submitted to Meta as abffst_thank_you, the run that sends it every
30 minutes between 07:00 and 19:59 (editable in Django admin, Periodic tasks), and a "skip" on the four cases that
look like the team's own test runs until the PI confirms them (a case's metadata "thank_you" -> "skip")."""

from django.db import migrations, models

NAME = "Thank participants who completed"
WORDING = (
    "Dear {{1}},\n\nThank you for completing the {{2}} for my doctoral study at Chinhoyi University of Technology, which "
    "is developing and validating the Agribusiness Bankability Index (ABI) and the ABF-FST framework in Zimbabwe.\n\nI "
    "appreciate the time and thought you gave to sharing your organisation's experiences. Your contribution helps the "
    "tools reflect the real financing needs, challenges and opportunities of agribusinesses.\n\nWhen the study is "
    "complete, I would be pleased to send you a summary of the findings, presented in aggregate with participants' "
    "identities protected. I also plan a stakeholder workshop to discuss the findings; details will follow once "
    "confirmed.\n\nWould you like the findings summary, a workshop invitation, or both? Tap a button below. This is "
    "optional, does not affect how your responses are treated, and taking part does not permit you to be identified "
    "publicly.\n\nHappyson Saina, PhD Researcher, Chinhoyi University of Technology\nStudy website: "
    "https://agribizframework.com/"
)
# Carry the PI's or the developer's own names or numbers (18 Oct 2026); not thanked until the PI says they are real.
POSSIBLE_TESTS = ["SID-2026-000001", "SID-2026-000002", "SID-2026-000005", "SID-2026-000062"]


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    daytime, _ = CrontabSchedule.objects.get_or_create(minute="*/30", hour="7-19", day_of_week="*", day_of_month="*",
                                                       month_of_year="*")
    PeriodicTask.objects.get_or_create(name=NAME, defaults={"crontab": daytime, "enabled": True,
                                                            "task": "apps.messaging.tasks.send_due_thanks_task"})
    apps.get_model("messaging", "MessageTemplate").objects.update_or_create(
        name="thank_you_whatsapp", defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": WORDING})
    SampleCase = apps.get_model("sampling", "SampleCase")
    for case in SampleCase.objects.filter(sample_id__in=POSSIBLE_TESTS):
        meta = dict(case.metadata or {})
        meta.setdefault("thank_you", {"skip": "possible test case (the team's own name or number); PI to confirm"})
        case.metadata = meta
        case.save(update_fields=["metadata"])


def unseed(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=NAME).delete()
    apps.get_model("messaging", "MessageTemplate").objects.filter(name="thank_you_whatsapp").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0017_intro_wording_v2"),
        ("django_celery_beat", "0001_initial"),
        ("sampling", "0007_replacement_policy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inboundmessage",
            name="kind",
            field=models.CharField(choices=[("YES", "Yes"), ("NO", "No"), ("PHONE", "Wants to answer by phone"), ("PREF", "Findings / workshop choice"), ("OTHER", "Other")], default="OTHER", max_length=8),
        ),
        migrations.AlterField(
            model_name="providermessage",
            name="purpose",
            field=models.CharField(choices=[("INVITATION", "Invitation"), ("REMINDER", "Reminder"), ("INTRODUCTION", "Introduction (ask first)"), ("REPLY", "Reply in a conversation"), ("MESSAGE", "Message written by the team"), ("THANK_YOU", "Thank you for taking part"), ("OTHER", "Other")], max_length=16),
        ),
        migrations.RunPython(seed, unseed),
    ]
