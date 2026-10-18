"""The PI's corrected introductions (approved 18 Oct 2026), submitted to Meta as abffst_intro_v3 and abffst_kii_intro_v3
in place of the v2 wording of migration 0017: TWILIO_WA_CONTENT_INTRO_NEXT / _KII_INTRO_NEXT now hold the v3 SIDs, and
these rows (the portal's copy, shown on the conversation timeline) carry the v3 text. A change here must also be
re-approved by Meta."""
from django.db import migrations

WORDING = {
    "outreach_intro_whatsapp_v2": 'Dear {{1}},\n\nI am Happyson Saina, a PhD researcher in Strategic Management at Chinhoyi University of Technology.\n\nPurpose: to examine how financing models and enterprise capabilities shape agribusiness access to finance and food systems transformation in Zimbabwe, and to develop and validate:\n• An Agribusiness Bankability Index (ABI) on enterprises’ readiness to access and use finance.\n• An ABF-FST framework to guide financing and support for resilient agrifood businesses.\n\nWhy participate? Your experience, even without external finance, helps identify barriers and practical improvements.\n\nParticipation: A 15–25-minute questionnaire via a personal link. Voluntary and confidential; you may stop at any time. Academic research, not a funding application or credit assessment.\n\nStudy background: https://agribizframework.com/\n\nMay I send the information sheet and your personal link? Reply YES or NO. YES is not consent; consent comes before the questionnaire.\n\nQuestions: Happyson Saina, 0773943709',
    "kii_outreach_intro_whatsapp_v2": 'Dear {{1}},\n\nI am Happyson Saina, PhD researcher in Strategic Management at Chinhoyi University of Technology. I invite a knowledgeable representative of your organisation to take part.\n\nPurpose: to examine how financing models, capabilities and institutions shape agribusiness bankability and food systems transformation in Zimbabwe, and to develop and validate:\n• An Agribusiness Bankability Index (ABI) on enterprise financing readiness.\n• An ABF-FST framework to guide financing and support for resilient agrifood businesses.\n\nWhy participate? Your insights help explain financing barriers and workable solutions.\n\nParticipation: About 30 minutes, in writing via a personal link or by phone. Voluntary and confidential; stop anytime. Academic research, not a funding application or credit assessment.\n\nStudy background: https://agribizframework.com/\n\nMay I send the information sheet and your personal link? Reply YES or NO. YES is not consent; consent comes before participation.\n\nQuestions: Happyson Saina, 0773943709',
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    for name, body in WORDING.items():
        MessageTemplate.objects.update_or_create(name=name, defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": body})


class Migration(migrations.Migration):
    dependencies = [("messaging", "0018_thank_you")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
