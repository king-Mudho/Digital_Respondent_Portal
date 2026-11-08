from django.core.management.base import BaseCommand, CommandError

from apps.kobo.pilot import PilotError, counts, sync


class Command(BaseCommand):
    help = "Copy the ZAS 2026 pilot submissions from KoboToolbox into the pilot strand (apps/kobo/pilot.py). Safe to re-run."

    def handle(self, *args, **options):
        try:
            stats = sync()
        except PilotError as exc:
            raise CommandError(str(exc)) from exc
        for form, s in stats.items():
            self.stdout.write(f"{form}: {s['added']} added, {s['updated']} updated, {s['gone']} no longer in KoboToolbox")
        self.stdout.write(f"Counted now: {counts()}")
