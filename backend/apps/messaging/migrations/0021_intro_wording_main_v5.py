"""Main-400 introduction v5 (PI, 18 Oct 2026), exactly as the PI wrote it (986 characters); submitted to Meta as
abffst_intro_v5 (TWILIO_WA_CONTENT_INTRO_NEXT). The portal's copy of the wording, shown on the conversation timeline.
A change here must also be re-approved by Meta."""
from django.db import migrations

BODY = 'Dear {{1}},\n\nI am Happyson Saina, a PhD researcher at Chinhoyi University of Technology.\n\nThis study examines how financing models and enterprise capabilities affect agribusiness access to finance and food systems transformation in Zimbabwe. It will develop and validate:\n• Agribusiness Bankability Index: assessing readiness to access and use of finance and support needs.\n• ABF-FST: a framework guiding finance and support for productive, inclusive, resilient agrifood businesses.\n\nYour experience, will help identify barriers and inform recommendations for financiers, policymakers and support bodies.\n\nThe questionnaire takes 15–25 minutes via a personal link. Participation is voluntary and confidential; you may stop anytime. This is research, not a funding application or credit assessment.\n\nBackground: https://agribizframework.com/\n\nMay I send the information sheet and link? Reply YES or NO. YES is not study consent; consent is sought before you begin.\n\nQuestions: 0773943709'


def seed(apps, schema_editor):
    apps.get_model("messaging", "MessageTemplate").objects.update_or_create(
        name="outreach_intro_whatsapp_v2", defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": BODY})


class Migration(migrations.Migration):
    dependencies = [("messaging", "0020_intro_wording_main_v4")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
