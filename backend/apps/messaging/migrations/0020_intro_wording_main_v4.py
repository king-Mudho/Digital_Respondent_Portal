"""Main-400 introduction v4 (PI, 18 Oct 2026): the ABI line exactly as the PI wrote it, with two small trims so the
template stays within WhatsApp's 1,024 characters; submitted to Meta as abffst_intro_v4 (TWILIO_WA_CONTENT_INTRO_NEXT).
The portal's copy of the wording, shown on the conversation timeline. A change here must also be re-approved by Meta."""
from django.db import migrations

BODY = 'Dear {{1}},\n\nI am Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University of Technology.\n\nPurpose: to examine how financing models and enterprise capabilities shape agribusiness access to finance and food systems transformation in Zimbabwe, and to develop and validate:\n• An Agribusiness Bankability Index (ABI) to identify enterprises’ readiness to access and use finance, and areas needing support.\n• An ABF-FST framework to guide financing and support for resilient agrifood businesses.\n\nWhy participate? Your experience, even without external finance, helps identify barriers and improvements.\n\nParticipation: A 15–25-minute questionnaire via a personal link. Voluntary and confidential; stop anytime. Academic research, not a funding application or credit assessment.\n\nStudy background: https://agribizframework.com/\n\nMay I send the information sheet and your personal link? Reply YES or NO. YES is not consent; consent comes before the questionnaire.\n\nQuestions: Happyson Saina, 0773943709'


def seed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.update_or_create(
        name="outreach_intro_whatsapp_v2", defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": BODY})


class Migration(migrations.Migration):
    dependencies = [("messaging", "0019_intro_wording_v3")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
