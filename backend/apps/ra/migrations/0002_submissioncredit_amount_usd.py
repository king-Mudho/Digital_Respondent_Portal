"""Each credited completion earns its RA a commission (PI, 23 Nov 2026). Credits already recorded are paid at the
rate in force today, settings.RA_COMMISSION_USD; uncredited ones earn nothing."""

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


def backfill(apps, schema_editor):
    SubmissionCredit = apps.get_model("ra", "SubmissionCredit")
    rate = Decimal(str(settings.RA_COMMISSION_USD)).quantize(Decimal("0.01"))
    SubmissionCredit.objects.exclude(kind="UNCREDITED").exclude(ra=None).update(amount_usd=rate)


class Migration(migrations.Migration):
    dependencies = [("ra", "0001_initial")]

    operations = [
        migrations.AddField(model_name="submissioncredit", name="amount_usd",
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=8)),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
