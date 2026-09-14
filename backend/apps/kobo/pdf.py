"""
A readable PDF of one completed KoboToolbox submission.

Built from the deployed form itself (the asset's XLSForm content: labels,
groups, choice lists), so the same renderer serves the Questionnaire, the KII
Guide and the Document Analysis Tool, and a revised form needs no code change.
Questions the respondent was never shown (empty answers) are left out, choice
codes are printed as their labels, and repeat groups print once per entry.

Never includes an ABI score, band or financing language (AGENTS.md ground
rule 3) -- it prints only what was entered in the form.
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SKIPPED_TYPES = {
    "note", "hidden", "calculate", "start", "end", "today", "username", "deviceid", "audit",
    "begin_repeat", "end_repeat", "begin repeat", "end repeat",
}
HEADER = colors.HexColor("#1B365D")
MUTED = colors.HexColor("#5B6573")
RULE = colors.HexColor("#D5DAE1")


def _label(row_or_choice: dict) -> str:
    label = row_or_choice.get("label")
    if isinstance(label, list):
        label = next((item for item in label if item), "")
    return str(label or row_or_choice.get("name") or row_or_choice.get("$autoname") or "")


def _type_parts(row: dict) -> tuple[str, str | None]:
    row_type = (row.get("type") or "").strip()
    if " " in row_type:
        base, list_name = row_type.split(" ", 1)
        return base, list_name.strip()
    return row_type, row.get("select_from_list_name")


class _Form:
    def __init__(self, content: dict):
        self.survey = content.get("survey", [])
        self.choices: dict[tuple[str, str], str] = {
            (c.get("list_name"), str(c.get("name") or c.get("$autovalue"))): _label(c)
            for c in content.get("choices", [])
        }

    def answer_text(self, row: dict, value) -> str:
        base, list_name = _type_parts(row)
        if base == "select_one":
            return self.choices.get((list_name, str(value)), str(value))
        if base == "select_multiple":
            return "; ".join(self.choices.get((list_name, code), code) for code in str(value).split())
        if base in ("start", "end", "dateTime", "datetime"):
            try:
                return datetime.fromisoformat(str(value)).strftime("%d %b %Y %H:%M")
            except ValueError:
                return str(value)
        return str(value)


def _xpath(row: dict, path: list[str]) -> str:
    return row.get("$xpath") or "/".join([*path, row.get("name") or row.get("$autoname") or ""])


def _sections(form: _Form, payload: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(section title, [(question, answer), ...]), ...] in form order."""
    sections: list[tuple[str, list[tuple[str, str]]]] = [("", [])]
    path: list[str] = []
    rows = form.survey
    i = 0
    while i < len(rows):
        row = rows[i]
        base, _ = _type_parts(row)
        kind = (row.get("type") or "").strip().replace(" ", "_")  # "begin group" == "begin_group"
        name = row.get("name") or row.get("$autoname") or ""
        if kind == "begin_group":
            path.append(name)
            title = _label(row)
            if title and title != name:
                sections.append((title, []))
        elif kind == "end_group":
            if path:
                path.pop()
        elif kind == "begin_repeat":
            repeat_xpath = _xpath(row, path)
            depth, j = 1, i + 1
            while j < len(rows) and depth:
                t = (rows[j].get("type") or "").replace(" ", "_")
                depth += 1 if t == "begin_repeat" else -1 if t == "end_repeat" else 0
                j += 1
            inner = rows[i + 1: j - 1]
            entries = payload.get(repeat_xpath) or []
            for n, entry in enumerate(entries if isinstance(entries, list) else [], start=1):
                items = []
                for sub in inner:
                    sub_base, _ = _type_parts(sub)
                    sub_kind = (sub.get("type") or "").strip().replace(" ", "_")
                    if sub_base in SKIPPED_TYPES or sub_kind.startswith(("begin_", "end_")):
                        continue
                    value = entry.get(_xpath(sub, [*path, row.get("name", "")]))
                    if value not in (None, ""):
                        items.append((_label(sub), form.answer_text(sub, value)))
                if items:
                    sections.append((f"{_label(row)} {n}", items))
            i = j
            continue
        elif base not in SKIPPED_TYPES and not kind.startswith(("begin_", "end_")):
            value = payload.get(_xpath(row, path))
            if value not in (None, ""):
                sections[-1][1].append((_label(row), form.answer_text(row, value)))
        i += 1
    return [(title, items) for title, items in sections if items]


def render_submission_pdf(*, form_content: dict, payload: dict, form_title: str, record_label: str) -> bytes:
    form = _Form(form_content)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=15,
                                 textColor=HEADER, alignment=TA_LEFT, spaceAfter=2)
    meta_style = ParagraphStyle("m", parent=styles["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    section_style = ParagraphStyle("s", parent=styles["Heading3"], fontSize=10.5, textColor=HEADER,
                                   spaceBefore=10, spaceAfter=4, keepWithNext=1)
    q_style = ParagraphStyle("q", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=MUTED)
    a_style = ParagraphStyle("a", parent=styles["Normal"], fontSize=9.5, leading=12.5)

    submitted = payload.get("_submission_time") or payload.get("end") or ""
    story = [
        Paragraph(escape(form_title), title_style),
        Paragraph(escape(f"{record_label} · submitted {str(submitted)[:16].replace('T', ' ')} UTC · "
                         f"KoboToolbox record {payload.get('_id', '')}"), meta_style),
        Paragraph("Confidential research record. For the ABF-FST research team and the participant only.",
                  meta_style),
        Spacer(1, 6),
    ]

    for title, items in _sections(form, payload):
        rows = [[Paragraph(escape(q), q_style), Paragraph(escape(a).replace("\n", "<br/>"), a_style)] for q, a in items]
        table = Table(rows, colWidths=[72 * mm, 108 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        if title:
            story.append(Paragraph(escape(title), section_style))  # keepWithNext: never orphaned
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 10 * mm, f"{form_title} · {record_label}")
        canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"{form_title} - {record_label}", author="ABF-FST Research Operations Centre",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
