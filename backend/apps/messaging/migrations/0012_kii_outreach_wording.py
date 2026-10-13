"""Wording for "ask first" introductions to KII informants (PI request, 2026-10-14; apps/messaging/outreach.py).
Editable in Django admin (Message templates) without a redeploy. "{org}" is replaced by who the message is for -- the
named informant and organisation, or the organisation alone while no informant is named -- and "{wa_link}" by the
tap-to-reply link to the study's WhatsApp number. The two *_whatsapp texts are a copy of what is submitted to Meta as
Twilio Content templates (TWILIO_WA_CONTENT_KII_INTRO and _REMINDER), written in the PI's own voice like the approved
Main-400 introduction: the portal sends the approved template, not this text, so a change here must also be
re-approved there."""
from django.db import migrations

SIGN_OFF = "Happyson Saina\nPhD Researcher, Chinhoyi University of Technology"
WORDING = {
    "kii_outreach_intro_whatsapp": (
        "Good day, {{1}}. My name is Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University "
        "of Technology.\n\nI am conducting a study to develop an Agribusiness Bankability Index (ABI) and an Agribusiness "
        "Bankability Framework for Food Systems Transformation (ABF-FST) in Zimbabwe. It examines how financing models "
        "can improve agribusiness access to finance and support food systems development.\n\nBecause of your "
        "organisation's role in agribusiness finance and the agrifood sector, I would value your views in a confidential "
        "key informant interview of about 30 minutes. You can complete it in your own time using a personal link, or "
        "by phone if you prefer.\n\nParticipation is voluntary and confidential. This is an academic study, not an "
        "application for funding.\n\nMay I send you the participant information and interview link? Please reply YES "
        f"or NO.\n\n{SIGN_OFF}"
    ),
    "kii_outreach_intro_reminder_whatsapp": (
        "Good day, {{1}}. This is a reminder from Happyson Saina, PhD researcher at Chinhoyi University of Technology, "
        "about a confidential key informant interview (about 30 minutes) for the ABF-FST study on agribusiness finance "
        "and food systems in Zimbabwe. Participation is voluntary and confidential, and it is not an application for "
        "funding.\n\nMay I send you the participant information and interview link? Please reply YES or NO.\n\n"
        f"{SIGN_OFF}"
    ),
    "kii_outreach_intro_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): {org}, we would value your views in a confidential "
        "key informant interview (about 30 min). To take part, reply YES on WhatsApp: {wa_link} Questions: 0773943709."
    ),
    "kii_outreach_intro_reminder_sms": (
        "ABF-FST research study (Chinhoyi University of Technology): a reminder for {org} about a key informant "
        "interview (about 30 min). To take part, reply YES on WhatsApp: {wa_link} Questions: 0773943709."
    ),
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for name, body in WORDING.items():
        channel = "SMS" if name.endswith("_sms") else "WHATSAPP"
        MessageTemplate.objects.get_or_create(name=name, defaults={"channel": channel, "category": "UTILITY", "body": body})


def unseed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(name__in=list(WORDING)).delete()


class Migration(migrations.Migration):
    dependencies = [("messaging", "0011_outreach_kii_record")]
    operations = [migrations.RunPython(seed, unseed)]
