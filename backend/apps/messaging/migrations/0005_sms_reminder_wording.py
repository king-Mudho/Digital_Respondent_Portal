"""SMS versions of the Day 2 and Day 7 reminders (2026-10-07), for automatic sending through Twilio.

The reminders were written for WhatsApp and say "reply here if you have questions". Two-way SMS is not available in
Zimbabwe, so by SMS that reply would go nowhere; these say to call the study number instead and otherwise keep the
approved wording. Editable in Django admin (Message templates) without a redeploy; services.sms_reminder_text() uses
"<reminder name>_sms" when it exists."""

from django.db import migrations

SMS = {
    "drp_reminder_day2_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): a reminder about the invitation sent to your "
        "organisation. Please use the link you were sent to take part. Questions? Call 0773943709."
    ),
    "drp_reminder_day7_final_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): a final reminder about the invitation sent to "
        "your organisation. If you would still like to take part, please use the link you were sent. Thank you."
    ),
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for name, body in SMS.items():
        MessageTemplate.objects.get_or_create(name=name, defaults={"channel": "SMS", "category": "UTILITY", "body": body})


def unseed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(name__in=list(SMS)).delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0004_provider_message")]

    operations = [migrations.RunPython(seed, unseed)]
