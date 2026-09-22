"""Flags likely test/pilot data on production, using the same patterns found and cleaned up by hand on
2026-09-22: an empty pre-interview profile stub, a KII or respondent contact whose name/email matches a
staff account, a case that moved from invited to QA-passed implausibly fast for real fieldwork, a document
with an uploaded file sitting unsubmitted, and an audit event whose own metadata names a user but whose
`user` field is still blank (a residual instance of the gap fixed in apps/audit/utils.py).

The checks themselves live in apps/audit/services.py, shared with the daily Celery task
(apps/audit/tasks.py:check_test_data_smells_task) that emails this same report to the PI admins.

Never deletes or changes anything -- read-only. A human decides what, if anything, to act on, the same way
the 2026-09-22 cleanup was scoped and confirmed step by step before anything was touched.

Run: manage.py check_test_data_smells [--since YYYY-MM-DD]
"""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from apps.audit.services import test_data_smells


class Command(BaseCommand):
    help = "Read-only scan for likely test/pilot data left on production (see module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--since", help="Only consider records created/changed on or after this date (YYYY-MM-DD).")

    def handle(self, *args, since=None, **opts):
        cutoff = parse_date(since) if since else None
        sections = test_data_smells(since=cutoff)
        total = 0
        for title, lines in sections:
            self.stdout.write(self.style.WARNING(f"\n-- {title} ({len(lines)}) --"))
            for line in lines:
                self.stdout.write(f"  {line}")
            total += len(lines)
        self.stdout.write(self.style.SUCCESS(f"\n{total} item(s) flagged for a human to look at. Nothing was changed."))
