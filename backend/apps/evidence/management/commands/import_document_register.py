"""
Imports the real, PI-approved Documentary Evidence register
(ABI_ABF-FST_Documentary_Evidence_Register_*.xlsx) into DocumentRecord.
document_id is still DB-generated (DOC-0001, ...), never taken from the
spreadsheet.

Unlike the QUAN and KII registers, this one has no separate "Reserve" list
-- a single "Document Register" sheet of 100 documents organised into 13
thematic Blocks (policy, banking, grains, poultry, ...), with no analogue
of Main-400/Reserve-400 or Core-60/Reserve-30. There is nothing to import
beyond it.

The register's "Type" column (61 distinct, highly granular values, e.g.
"Bank annual report", "Industry report", "Market platform") maps onto
DocumentRecord.document_type's three-way OFFICIAL/SECONDARY/PLATFORM split
via TYPE_MAP below: OFFICIAL covers government policy/legislation/
regulation and a named institution's own primary filings (its own annual
report, financial statements, official disclosures); SECONDARY covers
third-party analysis/diagnostics/benchmarks about a sector, not the
subject's own filing; PLATFORM covers data/market platforms. An
unrecognised Type raises rather than silently guessing.

Every register column with no dedicated model field (row #, thematic
Block, the register's own Link/Status retrieval notes) is preserved
losslessly in DocumentRecord.metadata -- nothing invented, nothing
discarded. "ABI / ABF-FST focus" populates construct_tags; "Financial
evidence" populates evidence_extract; "Why mandatory" populates
interpretive_memo.

Idempotent: re-running is a no-op for any row already imported (matched by
its own row number in metadata).
"""

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.evidence.models import DocumentRecord, DocumentType
from apps.evidence.services import generate_document_id

COL = dict(
    row_number=0, block=1, issuer_year=2, document=3, value_chain=4, type=5,
    financial_evidence=6, abi_focus=7, why_mandatory=8, link=9, status=10,
)

TYPE_MAP = {
    # Government/multilateral policy, strategy, legislation, regulation.
    "National strategy": DocumentType.OFFICIAL,
    "Sector strategy": DocumentType.OFFICIAL,
    "Policy framework": DocumentType.OFFICIAL,
    "Climate policy": DocumentType.OFFICIAL,
    "Drought strategy": DocumentType.OFFICIAL,
    "Industrial policy": DocumentType.OFFICIAL,
    "National vision": DocumentType.OFFICIAL,
    "Fiscal policy": DocumentType.OFFICIAL,
    "Fiscal review": DocumentType.OFFICIAL,
    "Food/nutrition strategy": DocumentType.OFFICIAL,
    "Legislation": DocumentType.OFFICIAL,
    "Infrastructure strategy": DocumentType.OFFICIAL,
    "Monetary policy": DocumentType.OFFICIAL,
    "Financial-inclusion strategy": DocumentType.OFFICIAL,
    "Regional strategy": DocumentType.OFFICIAL,
    "Continental strategy": DocumentType.OFFICIAL,
    "Institutional strategy": DocumentType.OFFICIAL,
    "Value-chain strategy": DocumentType.OFFICIAL,
    "Agricultural policy framework": DocumentType.OFFICIAL,
    "MDB strategy": DocumentType.OFFICIAL,
    "Regulation": DocumentType.OFFICIAL,
    "Market regulation": DocumentType.OFFICIAL,
    "Continental declaration": DocumentType.OFFICIAL,
    "Trade agreement": DocumentType.OFFICIAL,
    # A named institution's own primary-source filing.
    "Bank annual report": DocumentType.OFFICIAL,
    "Bank financial results": DocumentType.OFFICIAL,
    "Bank financial statements": DocumentType.OFFICIAL,
    "Financial-services results": DocumentType.OFFICIAL,
    "Bank/fintech financials": DocumentType.OFFICIAL,
    "DFI annual financials": DocumentType.OFFICIAL,
    "DFI financials": DocumentType.OFFICIAL,
    "DFI annual report": DocumentType.OFFICIAL,
    "Company annual report": DocumentType.OFFICIAL,
    "Company financial results": DocumentType.OFFICIAL,
    "Company financials": DocumentType.OFFICIAL,
    "Company institutional evidence": DocumentType.OFFICIAL,
    "Company/institution evidence": DocumentType.OFFICIAL,
    "Company evidence": DocumentType.OFFICIAL,
    "Company report": DocumentType.OFFICIAL,
    "Company sustainability evidence": DocumentType.OFFICIAL,
    "Climate/ESG disclosure": DocumentType.OFFICIAL,
    "Credit application": DocumentType.OFFICIAL,
    "Investment product": DocumentType.OFFICIAL,
    # Official statistics/registries.
    "Official statistics": DocumentType.OFFICIAL,
    "Regulator statistics": DocumentType.OFFICIAL,
    "Regulator annual/statistical report": DocumentType.OFFICIAL,
    "Regulatory/registry framework": DocumentType.OFFICIAL,
    # Third-party analysis/diagnostics/benchmarks about the sector.
    "Regional competition/value-chain report": DocumentType.SECONDARY,
    "Programme/regulatory evidence": DocumentType.SECONDARY,
    "Private-sector diagnostic": DocumentType.SECONDARY,
    "Regional institutional report": DocumentType.SECONDARY,
    "Industry report": DocumentType.SECONDARY,
    "Trade report": DocumentType.SECONDARY,
    "DFI/project evidence": DocumentType.SECONDARY,
    "DFI advisory report": DocumentType.SECONDARY,
    "Trade finance report": DocumentType.SECONDARY,
    "Global industry report": DocumentType.SECONDARY,
    "Global programme report": DocumentType.SECONDARY,
    "DFI sector factsheet": DocumentType.SECONDARY,
    "Agricultural finance benchmark": DocumentType.SECONDARY,
    # Data/market platforms.
    "Market platform": DocumentType.PLATFORM,
}


class Command(BaseCommand):
    help = "Import the real Documentary Evidence register into DocumentRecord."

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

        stats = {"created": 0, "skipped_existing": 0}

        with transaction.atomic():
            ws = wb["Document Register"]
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if row[COL["row_number"]] is None:
                    continue
                self._import_row(row, row_num, stats)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Created {stats['created']}, skipped {stats['skipped_existing']} already-imported."
            + (" (DRY RUN -- nothing committed)" if dry_run else "")
        ))

    def _import_row(self, row, row_num, stats):
        source_row_number = row[COL["row_number"]]

        if DocumentRecord.objects.filter(metadata__source_row_number=source_row_number).exists():
            stats["skipped_existing"] += 1
            return

        type_raw = row[COL["type"]]
        document_type = TYPE_MAP.get(type_raw)
        if document_type is None:
            raise CommandError(f"Document Register row {row_num}: unrecognised Type {type_raw!r}.")

        abi_focus_raw = row[COL["abi_focus"]]
        construct_tags = [t.strip() for t in abi_focus_raw.split(";") if t.strip()] if abi_focus_raw else []

        doc = DocumentRecord(
            document_id=generate_document_id(),
            title=row[COL["document"]],
            author_or_speaker=row[COL["issuer_year"]] or "",
            document_type=document_type,
            value_chain=row[COL["value_chain"]] or "",
            construct_tags=construct_tags,
            evidence_extract=row[COL["financial_evidence"]] or "",
            interpretive_memo=row[COL["why_mandatory"]] or "",
            metadata={
                "source_row_number": source_row_number,
                "block": row[COL["block"]] or "",
                "type_raw": type_raw,
                "link": row[COL["link"]] or "",
                "retrieval_status": row[COL["status"]] or "",
            },
        )
        doc.full_clean()
        doc.save()
        stats["created"] += 1
