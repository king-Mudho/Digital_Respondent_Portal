from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sampling", "0003_merge_duplicate_strata"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="stratumdefinition",
            constraint=models.UniqueConstraint(
                fields=["province", "actor_family", "value_chain", "size_class"],
                name="unique_stratum_definition_combo",
            ),
        ),
    ]
