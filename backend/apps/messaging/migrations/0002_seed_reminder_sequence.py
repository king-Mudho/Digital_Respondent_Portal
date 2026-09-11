"""
Seeds the default Day 2 / Day 7 automated reminder sequence
(docs/12_CONTACT_CRM_AND_MESSAGING.md). Day 0 "invitation" is the
invitation token itself, sent via invitations.services.issue_invitation --
not a separate MessageTemplate. Day 4-5 "telephone follow-up" is an RA task
(ContactEvent.next_action_date), not an automatable template send, so it
has no ReminderSequenceStep row here.

Templates are seeded with meta_approval_status=PENDING -- they cannot
actually be sent via WhatsApp until submitted to and approved by Meta
(3-5 business day review, docs/27_AGENT_EXECUTION_PLAN.md open item).
"""

from django.db import migrations


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    ReminderSequenceStep = apps.get_model("messaging", "ReminderSequenceStep")

    day2_template, _ = MessageTemplate.objects.get_or_create(
        name="drp_reminder_day2",
        defaults={
            "channel": "WHATSAPP",
            "category": "UTILITY",
            "meta_approval_status": "PENDING",
            "body": (
                "Hello, this is a reminder about the ABF-FST research study invitation "
                "sent to your organisation. Please use the link you were sent to take "
                "part, or reply here if you have questions."
            ),
        },
    )
    day7_template, _ = MessageTemplate.objects.get_or_create(
        name="drp_reminder_day7_final",
        defaults={
            "channel": "WHATSAPP",
            "category": "UTILITY",
            "meta_approval_status": "PENDING",
            "body": (
                "Hello, this is a final reminder about the ABF-FST research study "
                "invitation. If you would still like to take part, please use the link "
                "you were sent. Thank you."
            ),
        },
    )

    ReminderSequenceStep.objects.get_or_create(
        day_offset=2, defaults={"channel": "WHATSAPP", "template": day2_template, "label": "Day 2 reminder"}
    )
    ReminderSequenceStep.objects.get_or_create(
        day_offset=7, defaults={"channel": "WHATSAPP", "template": day7_template, "label": "Day 7 final routine attempt"}
    )


def unseed(apps, schema_editor):
    ReminderSequenceStep = apps.get_model("messaging", "ReminderSequenceStep")
    ReminderSequenceStep.objects.filter(day_offset__in=[2, 7]).delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
