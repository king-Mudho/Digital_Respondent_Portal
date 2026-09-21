"""Sends every reconciled (or deviation-released) pre-interview profile that is not yet in KoboToolbox.
Safe to re-run: a profile already sent is skipped unless --force."""

from django.core.management.base import BaseCommand

from apps.proit.kobo_submit import ProitKoboError, is_configured, push_profile
from apps.proit.models import PreProfile


class Command(BaseCommand):
    help = "Send finished PROIT profiles to the KoboToolbox PROIT Interview Profile form."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Send again even if already sent (creates a second record).")

    def handle(self, *args, force=False, **opts):
        if not is_configured():
            self.stdout.write("KOBO_PROIT_ASSET_UID / KOBO_ACCOUNT_USERNAME not set: nothing sent.")
            return
        counts = {}
        for profile in PreProfile.objects.filter(reconciliation_status__in=["RECONCILED", "UNRESOLVED"]).order_by("id"):
            try:
                result = push_profile(profile.pk, force=force)
            except ProitKoboError as exc:
                result = "failed"
                self.stderr.write(f"profile {profile.pk}: {exc}")
            counts[result] = counts.get(result, 0) + 1
        self.stdout.write(f"Done: {counts}")
