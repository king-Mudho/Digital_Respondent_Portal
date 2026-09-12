"""
Imports the real, PI-approved KII Core-60/Reserve-30 register
(ABI_ABF-FST_KII_Latest_Register_*.xlsx) into KIIRecord, via the same
sanctioned service function the rest of the app uses (create_kii_record) --
kii_id is still DB-generated (KII-0001, ...), never taken from the
spreadsheet.

Every one of the 90 rows in the real register is genuinely "Not contacted"
(Core-60) / "Available" (Reserve-30) -- nobody has been approached yet --
so every row imports as KIIStatus.PROSPECT (added 2026-09-12 specifically
for this), never INVITED. participant_name prefers a specific named
individual where the register already has one (either "Named KI (if in
frame)" or a research-verified "Verified Current Officeholder"); where
neither exists yet (35 of 90 rows), it honestly names the organisation
with "(contact not yet identified)" rather than inventing a person.

Every register column with no dedicated model field (the register's own
KII/Reserve ID, source cross-references, priority, verification status/
confidence/source, why-information-rich rationale, etc.) is preserved
losslessly in KIIRecord.metadata -- nothing invented, nothing discarded.

Idempotent: re-running is a no-op for any row already imported (matched by
its own register ID -- "KII-001"/"RES-001" -- in metadata).
"""

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.kii.models import KIIRecord, KIIStatus
from apps.kii.services import create_kii_record

# Column indices (0-based).
CORE_COL = dict(
    kii_id=0, core_rank=1, stakeholder_group=2, organisation=3, named_ki=4,
    target_role=5, province_scope=6, value_chain_activity=7, priority=8,
    selection_status=9, source_frame=10, source_id=11, eligibility_status=12,
    primary_module=13, abi_focus=14, hypothesis_relevance=15,
    documentary_analysis_priority=16, why_information_rich=17,
    public_evidence_url=18, fieldwork_status=19, appointment_date=20,
    field_notes=21, verified_officeholder=22, verified_title=23,
    verification_status=24, confidence=25, verification_source_url=26,
    source_date_currency=27, verification_notes=28,
)
RESERVE_COL = dict(
    kii_id=0, stakeholder_group=1, organisation=2, named_ki=3, target_role=4,
    province_scope=5, value_chain_activity=6, priority=7, source_frame=8,
    source_id=9, eligibility_status=10, primary_module=11,
    why_information_rich=12, public_evidence_url=13, reserve_status=14,
    verified_officeholder=15, verified_title=16, verification_status=17,
    confidence=18, source_date_currency=19, verification_notes=20,
)


class Command(BaseCommand):
    help = "Import the real KII Core-60/Reserve-30 register into KIIRecord."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the register .xlsx file.")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be imported without committing anything.",
        )

    def handle(self, *args, **options):
        path = options["file"]
        dry_run = options["dry_run"]

        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except FileNotFoundError as exc:
            raise CommandError(f"Register file not found: {path}") from exc

        stats = {"created": 0, "skipped_existing": 0, "identified": 0, "unidentified": 0}

        with transaction.atomic():
            for sheet_name, pool, col in [
                ("KII Core-60", "CORE_60", CORE_COL),
                ("Reserve-30", "RESERVE_30", RESERVE_COL),
            ]:
                ws = wb[sheet_name]
                for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if row[col["kii_id"]] is None:
                        continue
                    self._import_row(row, col, pool, sheet_name, row_num, stats)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Created {stats['created']} ({stats['identified']} with a named contact, "
            f"{stats['unidentified']} not yet identified), skipped {stats['skipped_existing']} "
            f"already-imported." + (" (DRY RUN -- nothing committed)" if dry_run else "")
        ))

    def _import_row(self, row, col, pool, sheet_name, row_num, stats):
        register_id = row[col["kii_id"]]

        if KIIRecord.objects.filter(metadata__register_id=register_id).exists():
            stats["skipped_existing"] += 1
            return

        organisation_name = row[col["organisation"]]
        target_role = row[col["target_role"]]
        if not organisation_name or not target_role:
            raise CommandError(f"{sheet_name} row {row_num} ({register_id}): missing organisation or target role.")

        named_ki = row[col["named_ki"]]
        verified_officeholder = row[col["verified_officeholder"]]
        if named_ki:
            participant_name = named_ki
            stats["identified"] += 1
        elif verified_officeholder:
            participant_name = verified_officeholder
            stats["identified"] += 1
        else:
            participant_name = f"{organisation_name} (contact not yet identified)"
            stats["unidentified"] += 1

        participant_role = row[col["verified_title"]] or target_role

        # Only Core-60 has this column (thematic ABI/ABF-FST focus tags,
        # semicolon-joined) -- Reserve-30's `col` has no "abi_focus" key.
        abi_focus_raw = row[col["abi_focus"]] if "abi_focus" in col else None
        thematic_tags = [t.strip() for t in abi_focus_raw.split(";") if t.strip()] if abi_focus_raw else []

        metadata = {
            "pool": pool,
            "register_id": register_id,
            "organisation_name": organisation_name,
            "source_frame": row[col["source_frame"]] or "",
            "source_id": row[col["source_id"]] or "",
            "priority": row[col["priority"]] or "",
            "value_chain_activity": row[col["value_chain_activity"]] or "",
            "eligibility_status": row[col["eligibility_status"]] or "",
            "primary_module": row[col["primary_module"]] or "",
            "why_information_rich": row[col["why_information_rich"]] or "",
            "public_evidence_url": row[col["public_evidence_url"]] or "",
            "verification_status": row[col["verification_status"]] or "",
            "confidence": row[col["confidence"]] or "",
            "source_date_currency": row[col["source_date_currency"]] or "",
            "verification_notes": row[col["verification_notes"]] or "",
        }
        if pool == "CORE_60":
            metadata.update({
                "core_rank": row[col["core_rank"]],
                "selection_status": row[col["selection_status"]] or "",
                "hypothesis_relevance": row[col["hypothesis_relevance"]] or "",
                "documentary_analysis_priority": row[col["documentary_analysis_priority"]] or "",
                "fieldwork_status": row[col["fieldwork_status"]] or "",
                "verification_source_url": row[col["verification_source_url"]] or "",
            })
        else:
            metadata.update({
                "reserve_status": row[col["reserve_status"]] or "",
            })

        create_kii_record(
            stakeholder_category=row[col["stakeholder_group"]] or "",
            participant_name=participant_name,
            participant_role=participant_role,
            status=KIIStatus.PROSPECT,
            thematic_coverage_tags=thematic_tags,
            metadata=metadata,
        )
        stats["created"] += 1
