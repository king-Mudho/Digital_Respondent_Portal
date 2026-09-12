from django.db import migrations, models


def merge_duplicate_strata(apps, schema_editor):
    """Found on research.agribizframework.com production: two StratumDefinition
    rows (different `code`, same province/actor_family/value_chain/size_class)
    existed for the same combination -- resolve_stratum_for_organisation()'s
    get_or_create() raised MultipleObjectsReturned the first time it ran
    against real data, since `code` being unique never actually enforced
    uniqueness on the four category fields together. For each duplicate
    combination, keep whichever row already has SampleCases pointing at it
    (or the lowest id if none do), re-point every SampleCase from the other
    rows onto it, and delete the surplus rows -- so the schema constraint
    added right after this can be applied cleanly.
    """
    StratumDefinition = apps.get_model("sampling", "StratumDefinition")
    SampleCase = apps.get_model("sampling", "SampleCase")

    seen = {}
    for stratum in StratumDefinition.objects.order_by("id"):
        key = (stratum.province, stratum.actor_family, stratum.value_chain, stratum.size_class)
        if key not in seen:
            seen[key] = stratum
            continue

        kept = seen[key]
        if not SampleCase.objects.filter(stratum=kept).exists() and SampleCase.objects.filter(stratum=stratum).exists():
            kept, stratum = stratum, kept
            seen[key] = kept

        SampleCase.objects.filter(stratum=stratum).update(stratum=kept)
        stratum.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sampling", "0002_samplecase_assigned_ra"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_strata, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="stratumdefinition",
            constraint=models.UniqueConstraint(
                fields=["province", "actor_family", "value_chain", "size_class"],
                name="unique_stratum_definition_combo",
            ),
        ),
    ]
