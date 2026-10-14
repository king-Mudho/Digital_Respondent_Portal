"""The automatic answer to someone who sends their invitation code to ask to answer by phone (2026-10-14,
apps/messaging/outreach.py). Editable in Django admin (Message templates) without a redeploy."""
from django.db import migrations

TEXT = ("Thank you. A member of the research team will call you to go through the questionnaire by phone. "
        "Questions: Happyson Saina, 0773943709.")


def seed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.get_or_create(
        name="outreach_phone_requested", defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": TEXT})


def unseed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(name="outreach_phone_requested").delete()


class Migration(migrations.Migration):
    dependencies = [("messaging", "0013_inbound_attachments_phone_kind")]
    operations = [migrations.RunPython(seed, unseed)]
