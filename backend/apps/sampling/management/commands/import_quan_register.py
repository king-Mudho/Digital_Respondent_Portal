"""
Imports the real, PI-approved QUAN Main-400/Reserve-400 sampling register
(ABI_ABF-FST_QUAN_Latest_Register_*.xlsx) into Organisation/SampleCase,
via the same sanctioned service functions the admin UI uses
(create_organisation, resolve_stratum_for_organisation, create_sample_case)
-- Master_ID/Sample_ID are still DB-generated, never taken from the
spreadsheet (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).

The register's own free-text category labels ("Bulawayo", "Aggregation /
Market / Retail", "Micro") are mapped onto this system's real,
PI-approved enum values (2026-09-12 schema fix) via the dictionaries
below, built directly from every distinct value actually found in the
register -- an unrecognised label raises rather than silently guessing.

Every register column with no dedicated model field (source ABI Master_ID,
Priority, QUAN Eligibility, Desk Verification Gate, Preferred Respondent,
Source Registers, Verification Evidence, Deployment Status, Selection
Method, the granular Actor/Stratum sub-classification) is preserved
losslessly in Organisation.metadata / SampleCase.metadata -- nothing
invented, nothing discarded.

Idempotent: re-running is a no-op for any organisation already imported
(matched by its source ABI Master_ID in metadata), so this is safe to run
more than once against the same database.
"""

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contacts.models import Respondent
from apps.sampling.models import Organisation, SampleCase, SampleType
from apps.sampling.services import create_organisation, create_sample_case, resolve_stratum_for_organisation

PROVINCE_MAP = {
    "Bulawayo": "BULAWAYO",
    "Harare": "HARARE",
    "Manicaland": "MANICALAND",
    "Mashonaland Central": "MASHONALAND_CENTRAL",
    "Mashonaland East": "MASHONALAND_EAST",
    "Mashonaland West": "MASHONALAND_WEST",
    "Masvingo": "MASVINGO",
    "Matabeleland North": "MATABELELAND_NORTH",
    "Matabeleland South": "MATABELELAND_SOUTH",
    "Midlands": "MIDLANDS",
}

ACTOR_FAMILY_MAP = {
    "Aggregation / Market / Retail": "AGGREGATION_MARKET_RETAIL",
    "Inputs / Mechanisation": "INPUTS_MECHANISATION",
    "Processing / Manufacturing": "PROCESSING_MANUFACTURING",
    "Producer / Primary": "PRODUCER_PRIMARY",
    "Services / Enabling": "SERVICES_ENABLING",
    "Finance / Insurance": "FINANCE_INSURANCE",
    "Institutional Commercial Unit": "INSTITUTIONAL_COMMERCIAL_UNIT",
    "Other / Verify": "OTHER_VERIFY",
}

SIZE_CLASS_MAP = {
    "Micro": "MICRO",
    "SME": "SME",
    "Unknown": "UNKNOWN",
    "Large / Corporate": "LARGE_CORPORATE",
    "Institutional / Other": "INSTITUTIONAL_OTHER",
}

# Column indices (0-based) shared by "Main Sample 400" and "Matched Reserve 400".
COL = dict(
    sample_id=0, master_id=1, organisation=2, province=3, district=4,
    actor_family=5, actor_stratum=6, value_chain=7, size_class=8, entity_type=9,
    priority=10, quan_eligibility=11, desk_verification_gate=12, preferred_respondent=13,
    existing_contact=14, email=15, phone=16, source_registers=17,
    verification_evidence=18, matched_counterpart_master_id=19, deployment_status=20,
    selection_method=21,
)


class Command(BaseCommand):
    help = "Import the real QUAN Main-400/Reserve-400 register into Organisation/SampleCase."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the register .xlsx file.")
        parser.add_argument("--year", type=int, default=2026)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be imported without committing anything.",
        )

    def handle(self, *args, **options):
        path = options["file"]
        year = options["year"]
        dry_run = options["dry_run"]

        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except FileNotFoundError as exc:
            raise CommandError(f"Register file not found: {path}") from exc

        stats = {"created": 0, "skipped_existing": 0, "respondents_created": 0, "matched": 0}

        with transaction.atomic():
            main_cases_by_source_id = {}
            reserve_cases_by_source_id = {}

            for sheet_name, sample_type, bucket in [
                ("Main Sample 400", SampleType.MAIN, main_cases_by_source_id),
                ("Matched Reserve 400", SampleType.RESERVE, reserve_cases_by_source_id),
            ]:
                ws = wb[sheet_name]
                for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if row[COL["sample_id"]] is None:
                        continue
                    case = self._import_row(row, row_num, sheet_name, sample_type, year, dry_run, stats)
                    bucket[row[COL["master_id"]]] = case

            # Second pass: wire up matched_case now that both sides exist.
            for source_id, case in main_cases_by_source_id.items():
                if case is None:
                    continue
                matched_source_id = case.metadata.get("matched_counterpart_master_id")
                counterpart = reserve_cases_by_source_id.get(matched_source_id)
                if counterpart is not None and case.matched_case_id != counterpart.id:
                    case.matched_case = counterpart
                    if not dry_run:
                        case.save(update_fields=["matched_case"])
                    stats["matched"] += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Created {stats['created']}, skipped {stats['skipped_existing']} already-imported, "
            f"{stats['respondents_created']} respondent contacts, {stats['matched']} matched pairs wired."
            + (" (DRY RUN -- nothing committed)" if dry_run else "")
        ))

    def _import_row(self, row, row_num, sheet_name, sample_type, year, dry_run, stats):
        source_master_id = row[COL["master_id"]]
        source_sample_id = row[COL["sample_id"]]

        existing = Organisation.objects.filter(metadata__source_master_id=source_master_id).first()
        if existing is not None:
            stats["skipped_existing"] += 1
            return SampleCase.objects.filter(organisation=existing, sample_type=sample_type).first()

        province_raw = row[COL["province"]]
        actor_family_raw = row[COL["actor_family"]]
        size_class_raw = row[COL["size_class"]] or "Unknown"

        province = PROVINCE_MAP.get(province_raw)
        actor_family = ACTOR_FAMILY_MAP.get(actor_family_raw)
        size_class = SIZE_CLASS_MAP.get(size_class_raw)
        if not (province and actor_family and size_class):
            raise CommandError(
                f"{sheet_name} row {row_num} ({source_sample_id}): unrecognised category value -- "
                f"province={province_raw!r} actor_family={actor_family_raw!r} size_class={size_class_raw!r}"
            )

        org = create_organisation(
            province=province,
            name=row[COL["organisation"]],
            entity_type=row[COL["entity_type"]] or "",
            district=row[COL["district"]] or "",
            actor_family=actor_family,
            value_chain=row[COL["value_chain"]] or "",
            size_class=size_class,
            metadata={"source_master_id": source_master_id},
        )
        stratum = resolve_stratum_for_organisation(org)
        case = create_sample_case(
            organisation=org, stratum=stratum, sample_type=sample_type, year=year,
            metadata={
                "source_sample_id": source_sample_id,
                "actor_stratum": row[COL["actor_stratum"]] or "",
                "priority": row[COL["priority"]] or "",
                "quan_eligibility": row[COL["quan_eligibility"]] or "",
                "desk_verification_gate": row[COL["desk_verification_gate"]] or "",
                "preferred_respondent": row[COL["preferred_respondent"]] or "",
                "source_registers": row[COL["source_registers"]] or "",
                "verification_evidence": row[COL["verification_evidence"]] or "",
                "matched_counterpart_master_id": row[COL["matched_counterpart_master_id"]],
                "deployment_status": row[COL["deployment_status"]] or "",
                "selection_method": row[COL["selection_method"]] or "",
            },
        )
        stats["created"] += 1

        existing_contact = row[COL["existing_contact"]]
        if existing_contact:
            Respondent.objects.create(
                sample_case=case,
                full_name=existing_contact,
                phone=row[COL["phone"]] or "",
                email=row[COL["email"]] or "",
            )
            stats["respondents_created"] += 1

        return case
