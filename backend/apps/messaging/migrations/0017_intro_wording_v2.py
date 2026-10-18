"""The PI's revised "ask first" introductions (approved by the PI 18 Oct 2026), submitted to Meta as Twilio Content
templates abffst_intro_v2 and abffst_kii_intro_v2 (TWILIO_WA_CONTENT_INTRO_NEXT / _KII_INTRO_NEXT). The portal sends
them, in place of the current ones, from the moment Meta approves them (outreach._intro_content). These rows are the
portal's own copy of that wording, shown on the conversation timeline: a change here must also be re-approved there."""
from django.db import migrations

QUESTIONS = "Questions: Happyson Saina, 0773943709"
TAIL = (
    "Voluntary and confidential; you may stop anytime. An academic study, not a funding application or credit "
    "assessment.\n\nBackground: https://agribizframework.com/\n\nMay I send the information sheet and your personal link? "
    "Reply YES or NO. A YES is not consent; consent is asked before you begin.\n\n" + QUESTIONS
)
OPENING = "Dear {{1}},\n\nI am Happyson Saina, PhD researcher in Strategic Management at Chinhoyi University of Technology. "
STUDY = ("my study on how financing models can improve agribusiness access to finance and food systems transformation in "
         "Zimbabwe.\n\n")
PURPOSE = (
    "*Purpose:* to develop and validate the Agribusiness Bankability Index (ABI), on enterprise readiness to access and "
    "use finance, and the ABF-FST framework, on how capabilities, financing and institutions can strengthen agrifood "
    "businesses.\n\n"
)
WORDING = {
    "outreach_intro_whatsapp_v2": (
        OPENING + "Your organisation has been selected for " + STUDY + PURPOSE
        + "*Why you:* your experience, whether or not you obtained finance, keeps the tools realistic.\n\n"
        + "*Taking part:* a questionnaire of about 15-25 minutes via a personal link. " + TAIL
    ),
    "kii_outreach_intro_whatsapp_v2": (
        OPENING + "I invite a knowledgeable representative of your organisation to " + STUDY + PURPOSE
        + "*Why you:* your experience shows what helps or blocks access to finance.\n\n"
        + "*Taking part:* about 30 minutes, in writing via a personal link or by telephone. " + TAIL
    ),
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for name, body in WORDING.items():
        MessageTemplate.objects.update_or_create(name=name, defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": body})


def unseed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.filter(name__in=list(WORDING)).delete()


class Migration(migrations.Migration):
    dependencies = [("messaging", "0016_providermessage_is_template")]
    operations = [migrations.RunPython(seed, unseed)]
