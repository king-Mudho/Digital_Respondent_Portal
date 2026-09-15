"""
Tidy respondent contacts created by import_quan_register (added 2026-09-15).

The importer put the register's whole "Existing Contact" cell -- numbers,
emails, notes -- into Respondent.full_name, left invisible zero-width spaces
in phone numbers, and never set a WhatsApp number. This moves each part to
its own field: a person's name when the cell has one (otherwise a clear
placeholder), a readable phone list, the first WhatsApp-reachable mobile,
and the email.

Only rows nobody has edited are touched: full_name still looks like contact
text and no role or eligibility decision has been recorded. The original
values are written to a JSON backup first, and the run is audited (ids and
counts only, never the numbers).

    manage.py clean_imported_contacts --dry-run
    manage.py clean_imported_contacts --backup-dir /srv/agribiz-drp/backups
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.utils import log_action
from apps.contacts.contact_text import clean, looks_like_contact_text, split_contact_text
from apps.contacts.models import Respondent


class _Run:
    pk = "clean_imported_contacts"


class Command(BaseCommand):
    help = "Split imported contact text into name, phone, WhatsApp number and email."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show the changes without saving.")
        parser.add_argument("--backup-dir", default=".", help="Where to write the JSON backup of the original values.")

    def handle(self, *args, dry_run=False, backup_dir=".", **options):
        candidates = [
            r for r in Respondent.objects.select_related("sample_case").order_by("id")
            if looks_like_contact_text(r.full_name) and not r.role_category and r.is_eligible is None
        ]
        changes = []
        for r in candidates:
            parts = split_contact_text(r.full_name, r.phone)
            new = {
                "full_name": parts.name,
                "phone": parts.phone,
                "whatsapp_number": clean(r.whatsapp_number) or parts.whatsapp,
                "email": clean(r.email) or parts.email,
            }
            old = {field: getattr(r, field) for field in new}
            if new != old:
                changes.append((r, old, new))

        for r, old, new in changes:
            self.stdout.write(f"{r.sample_case.sample_id} #{r.id}: " + "; ".join(
                f"{field} {old[field]!r} -> {new[field]!r}" for field in new if old[field] != new[field]))
        summary = {
            "respondents_changed": len(changes),
            "with_whatsapp_number": sum(1 for _, _, new in changes if new["whatsapp_number"]),
            "named": sum(1 for _, _, new in changes if not new["full_name"].startswith(("Organisation contact", "Contact to be"))),
        }
        self.stdout.write(self.style.SUCCESS(f"{summary}" + (" (DRY RUN -- nothing saved)" if dry_run else "")))
        if dry_run or not changes:
            return

        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S-%f")
        backup = Path(backup_dir) / f"imported-contacts-before-cleanup-{stamp}.json"
        backup.write_text(json.dumps(
            [{"id": r.id, "sample_id": r.sample_case.sample_id, **old} for r, old, _ in changes], indent=2, ensure_ascii=False))
        backup.chmod(0o600)

        with transaction.atomic():
            for r, _, new in changes:
                for field, value in new.items():
                    setattr(r, field, value)
                r.save(update_fields=[*new.keys(), "updated_at"])
            log_action("contacts.imported_contacts_cleaned", _Run(), {
                **summary, "respondent_ids": [r.id for r, _, _ in changes], "backup": str(backup),
            })
        self.stdout.write(self.style.SUCCESS(f"Saved. Original values backed up to {backup}"))
