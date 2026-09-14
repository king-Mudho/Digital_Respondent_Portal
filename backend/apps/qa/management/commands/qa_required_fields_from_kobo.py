from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.utils import log_action
from apps.kobo.client import KoboClient
from apps.qa.models import QARuleThreshold
from apps.qa.required_fields import required_field_names


class Command(BaseCommand):
    help = "Set the QA required_field_names threshold from the deployed Kobo questionnaire. Dry run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, apply=False, **options):
        names = required_field_names(KoboClient().fetch_form_survey())
        self.stdout.write(f"{len(names)} required fields: {', '.join(names)}")
        if not apply:
            self.stdout.write("Dry run -- pass --apply to save.")
            return
        threshold, _ = QARuleThreshold.objects.get_or_create(
            code="required_field_names", defaults={"value": [], "effective_from": timezone.now()},
        )
        previous = threshold.value
        threshold.value = names
        threshold.effective_from = timezone.now()
        threshold.save(update_fields=["value", "effective_from"])
        log_action("qa.threshold_changed", threshold, {
            "code": threshold.code, "previous_count": len(previous or []), "new_count": len(names),
            "source": "deployed Kobo form",
        })
        self.stdout.write(self.style.SUCCESS("Saved."))
