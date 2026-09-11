"""
Seeds QARuleThreshold rows from the proposed defaults in
docs/15_QA_AND_DATA_QUALITY.md -- flagged provisional pending PI sign-off,
proceeding on them per the user's Phase-0-defaults decision
(docs/27_AGENT_EXECUTION_PLAN.md "Open questions"). See
apps/qa/services.py DEFAULT_THRESHOLDS for the source of truth these mirror.
"""

from django.db import migrations
from django.utils import timezone

DEFAULT_THRESHOLDS = {
    "min_plausible_duration_seconds": 300,
    "max_plausible_duration_seconds": 5400,
    "max_missing_optional_fields_percent": 10,
    "duplicate_master_id_window_hours": 24,
    "logic_violation_hard_stop_rules": [],
    "logic_violation_soft_flag_rules": [],
    "mode_imbalance_alert_ratio": 0.70,
    "required_field_names": [],
    "optional_field_names": [],
}


def seed(apps, schema_editor):
    QARuleThreshold = apps.get_model("qa", "QARuleThreshold")
    now = timezone.now()
    for code, value in DEFAULT_THRESHOLDS.items():
        QARuleThreshold.objects.get_or_create(
            code=code, defaults={"value": value, "effective_from": now, "set_by": None}
        )


def unseed(apps, schema_editor):
    QARuleThreshold = apps.get_model("qa", "QARuleThreshold")
    QARuleThreshold.objects.filter(code__in=DEFAULT_THRESHOLDS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [("qa", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
