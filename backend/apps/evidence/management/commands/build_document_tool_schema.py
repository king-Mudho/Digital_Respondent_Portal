"""Parses the Document, Digital Platform & Media Analysis Tool's XLSForm into
a portable JSON schema checked in at apps/evidence/document_tool_schema.json.
That file -- not the xlsx, which lives outside the repo -- is the source of
truth both the AI drafting prompt (ai_coding.py) and the KoboToolbox
submission builder (kobo_submit.py) validate against, so a field name typo
or a stale choice list is caught immediately rather than silently building
an invalid submission.

Re-run this whenever the deployed XLSForm changes (docs/14):

    backend/.venv/Scripts/python.exe manage.py build_document_tool_schema \\
        "D:\\Mr Saina\\Final Interview Forms from September to November\\Kobo-ready 2026-09-14\\ABF-FST_Document_Digital_Platform_Media_Analysis_Tool_v2.0_KOBO.xlsx"
"""

import json
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError

OUT_PATH = Path(__file__).resolve().parents[2] / "document_tool_schema.json"

# Types that don't collect an answer -- excluded from the schema entirely
# (a "note" is instructional text). start/end/deviceid/today/username are
# metadata Kobo's own clients (Enketo/KoboCollect) fill in themselves, but a
# submission built by kobo_submit.py still needs their element *names* --
# which vary per form (the Documents tool calls its username field
# "coder_username"; the KII Guide calls its own "enumerator_username") --
# so they're captured separately below, in META_FIELD_TYPES, rather than
# silently dropped like a genuine "note".
META_FIELD_TYPES = {"start", "end", "deviceid", "today", "username"}
SKIP_TYPES = {"note", *META_FIELD_TYPES, "begin_group", "end_group", "begin_repeat", "end_repeat"}


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path")

    def handle(self, *args, **options):
        path = Path(options["xlsx_path"])
        if not path.exists():
            raise CommandError(f"{path} not found")

        wb = openpyxl.load_workbook(path)
        choices = self._parse_choices(wb["choices"])
        fields, groups = self._parse_survey(wb["survey"], choices)
        settings_row = self._parse_settings(wb["settings"])

        schema = {
            "form_id": settings_row["form_id"],
            "form_title": settings_row["form_title"],
            "version": settings_row["version"],
            "groups": groups,  # top-level group order, e.g. ["section_a", ...]
            "fields": fields,  # ordered list of field dicts, see _parse_survey
            "meta_fields": self._meta_fields,  # {"start": "start", "username": "coder_username", ...}
        }
        OUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"wrote {OUT_PATH} ({len(fields)} fields, {len(groups)} top-level groups)"))

    def _parse_choices(self, ws) -> dict[str, list[dict]]:
        choices: dict[str, list[dict]] = {}
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        for list_name, name, label in rows:
            if not list_name or not name:
                continue
            choices.setdefault(list_name, []).append({"code": str(name), "label": label or str(name)})
        return choices

    def _parse_settings(self, ws) -> dict:
        headers = [c.value for c in ws[1]]
        values = [c.value for c in ws[2]]
        return dict(zip(headers, values))

    def _parse_survey(self, ws, choices: dict) -> tuple[list[dict], list[str]]:
        fields: list[dict] = []
        top_level_groups: list[str] = []
        group_path: list[str] = []
        repeat_depth = 0  # a field inside a repeat can't be safely prefilled by name alone
        self._meta_fields: dict[str, str] = {}

        for row in ws.iter_rows(min_row=2, values_only=True):
            raw_type, name, label = (row[0] or "").strip() if row[0] else "", row[1], row[2]
            if not raw_type:
                continue
            type_key = raw_type.split()[0]  # "select_one xyz" -> "select_one"

            if type_key in META_FIELD_TYPES:
                self._meta_fields[type_key] = name
                continue
            if type_key in ("begin_group",):
                group_path.append(name)
                if len(group_path) == 1:
                    top_level_groups.append(name)
                continue
            if type_key == "end_group":
                if group_path:
                    group_path.pop()
                continue
            if type_key == "begin_repeat":
                group_path.append(name)
                repeat_depth += 1
                continue
            if type_key == "end_repeat":
                if group_path:
                    group_path.pop()
                repeat_depth -= 1
                continue
            if type_key in SKIP_TYPES:
                continue

            field = {
                "name": name,
                "path": "/".join([*group_path, name]),
                "label": label or "",
                "type": type_key,
                "in_repeat": repeat_depth > 0,
            }
            if type_key in ("select_one", "select_multiple"):
                list_name = raw_type.split(maxsplit=1)[1].strip()
                field["choices"] = choices.get(list_name, [])
                if not field["choices"]:
                    self.stdout.write(self.style.WARNING(f"no choices found for list '{list_name}' ({field['path']})"))
            fields.append(field)

        return fields, top_level_groups
