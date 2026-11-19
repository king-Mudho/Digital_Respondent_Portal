"""The message that goes with the study's information documents when a research assistant sends them to someone who
asked (PI, 19 Nov 2026; apps/clearance/brief.py). {name} is the person's name where one is on file, and the line with
{link} is kept only when the documents go as a link from the research assistant's own phone. Editable like every
other MessageTemplate; it is free text inside a conversation, not a Meta template, so no approval is needed."""
from django.db import migrations

BODY = (
    "Hello{name},\n\n"
    "Thank you for speaking with us. As you asked, here is information about the ABF-FST research study by "
    "Happyson Saina, a PhD researcher at Chinhoyi University of Technology Graduate Business School.\n\n"
    "Read it here: {link}\n\n"
    "Please read it in your own time. Taking part is voluntary, and you will be asked for your consent before any "
    "questions. If you have any questions, reply to this message or call Happyson Saina on 0773943709."
)


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("messaging", "MessageTemplate")
    MessageTemplate.objects.get_or_create(name="study_brief_message",
                                          defaults={"channel": "WHATSAPP", "category": "UTILITY", "body": BODY})


class Migration(migrations.Migration):
    dependencies = [("messaging", "0024_alter_providermessage_purpose")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
