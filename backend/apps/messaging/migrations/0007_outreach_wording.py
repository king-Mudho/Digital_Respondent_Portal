"""Wording for "ask first" introductions and the automatic replies (2026-10-07, apps/messaging/outreach.py).

All for the PI to approve and editable in Django admin (Message templates) without a redeploy. "{org}" is replaced by
the organisation's name and "{wa_link}" by the tap-to-reply link to the study's WhatsApp number. The two *_whatsapp
texts are a copy of what is submitted to Meta as Twilio Content templates (TWILIO_WA_CONTENT_INTRO and _REMINDER): the
portal sends the approved template, not this text, so a change here must also be re-approved there."""

from django.db import migrations

CONTACT = "Questions: Happyson Saina, 0773943709."

WORDING = {
    "outreach_intro_whatsapp": (
        "Hello, {{1}}. Chinhoyi University of Technology is carrying out the ABF-FST research study on agribusiness "
        "financing in Zimbabwe, and your organisation has been selected to take part. It is a voluntary, confidential "
        "questionnaire of about 15-25 minutes, and it produces no score or financing decision. Would you like to take "
        f"part? Reply YES and we will send your personal link, or NO if you would rather not. {CONTACT}"
    ),
    "outreach_intro_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): {org} has been selected for a voluntary, "
        "confidential questionnaire on agribusiness financing (about 15-25 min). To take part, reply YES on WhatsApp: "
        "{wa_link} Questions: 0773943709."
    ),
    "outreach_intro_reminder_whatsapp": (
        "Hello, {{1}}. A reminder about the ABF-FST research study at Chinhoyi University of Technology. Would you like "
        f"to take part? Reply YES to receive your personal link, or NO if you would rather not. {CONTACT}"
    ),
    "outreach_intro_reminder_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): a reminder for {org}. To take part, reply YES on "
        "WhatsApp: {wa_link} Questions: 0773943709."
    ),
    "outreach_declined_reply": "Thank you for letting us know. We will not contact you again about this study.",
    "outreach_auto_answer": (
        "Thank you for your message. A member of the research team will reply. To take part, reply YES; if you would "
        f"rather not, reply NO. {CONTACT}"
    ),
    "outreach_link_already_sent": (
        "Your personal link is in the message above. If you can't find it, call 0773943709 and we will help."
    ),
    "outreach_link_unavailable": (
        "Thank you. A member of the research team will contact you shortly with your personal link. "
        f"{CONTACT}"
    ),
    "outreach_unknown_number": f"Thank you for your message to the ABF-FST research study. {CONTACT}",
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for name, body in WORDING.items():
        channel = "SMS" if name.endswith("_sms") else "WHATSAPP"
        MessageTemplate.objects.get_or_create(name=name, defaults={"channel": channel, "category": "UTILITY", "body": body})


def unseed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(name__in=list(WORDING)).delete()


class Migration(migrations.Migration):

    dependencies = [("messaging", "0006_outreach")]

    operations = [migrations.RunPython(seed, unseed)]
