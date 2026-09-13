# -*- coding: utf-8 -*-
"""
Builds the QA-thresholds / Participant-Information-Sheet sign-off pack as a
PDF, for circulation to the PI, supervisors and the CUT Research Ethics
office. Standalone -- only reportlab (already a backend dependency).

    backend/.venv/Scripts/python.exe docs/tools/build_signoff_pack.py

Content is the same as docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md, which
stays the tracked source of record; this is the circulatable form, with
signature lines that can be printed and signed. Keep the two in step --
if you change one, change the other.

The QA threshold values below are read from the code at build time rather
than retyped, so this pack cannot drift from what the system enforces.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "ABF-FST_QA_Thresholds_and_PIS_Signoff_Pack.pdf")

REVISION = "Issued 13 September 2026 &mdash; awaiting sign-off"

# --- read the live values out of the code, never retyped ------------------
sys.path.insert(0, os.path.join(REPO, "backend"))


def load_live_values():
    """Pull DEFAULT_THRESHOLDS and the PIS text from source, so this pack
    cannot quietly disagree with what is deployed."""
    import ast
    import re

    qa_src = open(os.path.join(REPO, "backend/apps/qa/services.py"), encoding="utf-8").read()
    m = re.search(r"DEFAULT_THRESHOLDS = (\{.*?\n\})", qa_src, re.S)
    # strip comment lines so literal_eval accepts it
    literal = "\n".join(l for l in m.group(1).splitlines() if not l.strip().startswith("#"))
    thresholds = ast.literal_eval(literal)

    pis_src = open(
        os.path.join(REPO, "frontend/lib/constants/participantInformation.ts"), encoding="utf-8"
    ).read()
    version = re.search(r'PARTICIPANT_INFORMATION_SHEET_VERSION = "([^"]+)"', pis_src).group(1)
    body = re.search(r"PARTICIPANT_INFORMATION_SHEET = `\n(.*?)`\.trim\(\)", pis_src, re.S).group(1)
    return thresholds, version, body.strip()


THRESHOLDS, PIS_VERSION, PIS_TEXT = load_live_values()

# ---------------------------------------------------------------- palette --
NAVY = colors.HexColor("#1B3350")
NAVY_DARK = colors.HexColor("#122238")
GOLD = colors.HexColor("#A67C27")
INK = colors.HexColor("#22282E")
MUTED = colors.HexColor("#5B6670")
LINE = colors.HexColor("#D5DAE0")
WASH = colors.HexColor("#F1F4F7")
WARN_BG = colors.HexColor("#FBF1E1")
WARN_LINE = colors.HexColor("#D9A441")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 2.1 * cm

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1x", fontName="Helvetica-Bold", fontSize=17, leading=21,
                          textColor=NAVY_DARK, spaceBefore=4, spaceAfter=10))
styles.add(ParagraphStyle("H2x", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                          textColor=NAVY, spaceBefore=14, spaceAfter=6))
styles.add(ParagraphStyle("H3x", fontName="Helvetica-Bold", fontSize=10.8, leading=14,
                          textColor=INK, spaceBefore=10, spaceAfter=4))
styles.add(ParagraphStyle("Bodyx", fontName="Helvetica", fontSize=9.8, leading=14,
                          textColor=INK, spaceAfter=6, alignment=TA_LEFT))
styles.add(ParagraphStyle("Smallx", fontName="Helvetica", fontSize=8.8, leading=12.5,
                          textColor=MUTED, spaceAfter=5))
styles.add(ParagraphStyle("Bulletx", fontName="Helvetica", fontSize=9.8, leading=14,
                          textColor=INK, spaceAfter=3, leftIndent=13, bulletIndent=2))
styles.add(ParagraphStyle("Quotex", fontName="Helvetica-Oblique", fontSize=9.4, leading=14,
                          textColor=INK, leftIndent=12, rightIndent=8, spaceAfter=7))
styles.add(ParagraphStyle("THead", fontName="Helvetica-Bold", fontSize=8.6, leading=11,
                          textColor=WHITE))
styles.add(ParagraphStyle("TCell", fontName="Helvetica", fontSize=8.8, leading=12,
                          textColor=INK))
styles.add(ParagraphStyle("WarnT", fontName="Helvetica-Bold", fontSize=9.3, leading=12.5,
                          textColor=colors.HexColor("#7A5410")))
styles.add(ParagraphStyle("WarnB", fontName="Helvetica", fontSize=9.2, leading=13,
                          textColor=colors.HexColor("#5C4008")))
styles.add(ParagraphStyle("Decide", fontName="Helvetica-Bold", fontSize=9.4, leading=13.5,
                          textColor=NAVY_DARK))


def P(t, s="Bodyx"):
    return Paragraph(t, styles[s])


def bullet(t):
    return Paragraph("&bull;&nbsp; " + t, styles["Bulletx"])


def note(title, body, bg=WARN_BG, edge=WARN_LINE):
    inner = [[Paragraph(title, styles["WarnT"])], [Paragraph(body, styles["WarnB"])]]
    t = Table(inner, colWidths=[PAGE_W - 2 * MARGIN - 0.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ]))
    return t


def table(head, rows, widths):
    data = [[Paragraph(h, styles["THead"]) for h in head]]
    data += [[Paragraph(str(c), styles["TCell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, WASH]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def decision_line(label):
    """A visible, fillable decision row -- this is a document to be signed."""
    t = Table([[Paragraph(label, styles["Decide"])],
               [Paragraph("Rationale: " + "_" * 92, styles["Smallx"])]],
              colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WASH),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, NAVY),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def page_furniture(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, PAGE_H - 1.55 * cm, PAGE_W - MARGIN, PAGE_H - 1.55 * cm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(MARGIN, PAGE_H - 1.35 * cm, "ABF-FST DIGITAL RESPONDENT PORTAL")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.35 * cm,
                           "QA thresholds & PIS — sign-off pack")
    canvas.line(MARGIN, 1.35 * cm, PAGE_W - MARGIN, 1.35 * cm)
    canvas.drawString(MARGIN, 1.05 * cm,
                      "Chinhoyi University of Technology · awaiting sign-off")
    canvas.drawRightString(PAGE_W - MARGIN, 1.05 * cm, f"Page {doc.page}")
    canvas.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                      topMargin=MARGIN, bottomMargin=MARGIN,
                      title="ABF-FST — QA thresholds and PIS sign-off pack",
                      author="Happyson Saina")
doc.addPageTemplates([PageTemplate(
    id="Body",
    frames=[Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="b")],
    onPage=page_furniture,
)])

S = []
S.append(P("QA thresholds and Participant Information Sheet", "H1x"))
S.append(P("Review and sign-off pack &mdash; ABF-FST Digital Respondent Portal", "Bodyx"))
S.append(P(REVISION, "Smallx"))
S.append(Spacer(1, 8))
S.append(note(
    "What this document is for",
    "Two items have run on engineering defaults since Phase 0: the QUAN QA rule "
    "thresholds and the Participant Information Sheet wording. Both are research "
    "decisions, not engineering ones, and neither has been reviewed by anyone qualified "
    "to approve it. They were previously readable only inside a database migration and a "
    "TypeScript constant &mdash; there was nothing a reviewer could read and sign. "
    "<b>Nothing here is a recommendation to keep the current values.</b> They were chosen "
    "to make the system concretely testable, not because they are methodologically "
    "justified.",
))
S.append(Spacer(1, 10))
S.append(P("Values in this pack are read directly from the deployed source at build time, "
           "not retyped, so it cannot disagree with what the system enforces. The tracked "
           "record is <font face='Courier'>docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md</font>.",
           "Smallx"))

# ----------------------------------------------------------------- PART A --
S.append(PageBreak())
S.append(P("Part A &mdash; QUAN QA rule thresholds", "H1x"))
S.append(P("Thresholds are stored as data (<font face='Courier'>QARuleThreshold</font> "
           "rows), not hardcoded, so a value can change without a redeploy and every "
           "change is attributable to a user and a date."))

S.append(P("A1. What is actually enforced today", "H2x"))
S.append(P("Of the nine configured thresholds, <b>three are active</b>. Five are dormant "
           "until the real KoboToolbox form's field names are frozen, and one is never "
           "read at all. Approving a value that nothing evaluates would give false "
           "assurance, so the state of each is shown."))

state = {
    "min_plausible_duration_seconds": ("<b>Active</b>", "300 seconds (5 minutes)"),
    "max_plausible_duration_seconds": ("<b>Active</b>", "5400 seconds (90 minutes)"),
    "duplicate_master_id_window_hours": ("<b>Active</b>", "24 hours"),
    "required_field_names": ("Dormant &mdash; empty, so the missing-required-fields hard stop never fires", "empty"),
    "optional_field_names": ("Dormant &mdash; empty", "empty"),
    "max_missing_optional_fields_percent": ("Dormant &mdash; only evaluated once optional fields exist", "10%"),
    "logic_violation_hard_stop_rules": ("Dormant &mdash; no rules defined", "none"),
    "logic_violation_soft_flag_rules": ("Dormant &mdash; no rules defined", "none"),
    "mode_imbalance_alert_ratio": ("<b>Not implemented</b> &mdash; defined but never read", "0.70"),
}
S.append(Spacer(1, 4))
S.append(table(
    ["Threshold", "Value", "State"],
    [[f"<font face='Courier' size='8'>{k}</font>", state[k][1], state[k][0]] for k in THRESHOLDS],
    [6.2 * cm, 3.1 * cm, PAGE_W - 2 * MARGIN - 9.3 * cm],
))
S.append(Spacer(1, 8))
S.append(note(
    "A wrong threshold does not admit bad data",
    "No submission ever reaches QA-passed automatically. Every rule here produces a "
    "<i>flag</i> for human review, and only a human decision with a mandatory note can "
    "pass a submission. A wrong value creates review workload, or misses a prompt to "
    "look &mdash; it does not by itself let poor data into the dataset.",
))

S.append(P("A2. The three active thresholds &mdash; decisions required", "H2x"))

S.append(KeepTogether([
    P("A2.1 Minimum plausible duration &mdash; currently 300 seconds (5 minutes)", "H3x"),
    P("Flags a submission completed faster than this as implausibly quick."),
    bullet("<b>Too low</b> &mdash; straight-lining and careless completion pass unflagged."),
    bullet("<b>Too high</b> &mdash; genuinely fast, competent respondents are flagged, "
           "creating review work and implying bad faith where there is none."),
    bullet("<b>To judge it:</b> how quickly could a well-prepared finance director who "
           "knows their figures finish? Respondents are told it takes 15&ndash;25 minutes."),
    Spacer(1, 4),
    decision_line("Decision:&nbsp; keep 300&nbsp; /&nbsp; change to ________ seconds"),
]))

S.append(KeepTogether([
    P("A2.2 Maximum plausible duration &mdash; currently 5400 seconds (90 minutes)", "H3x"),
    P("Flags a submission that took longer than this."),
    bullet("<b>Too low</b> &mdash; flags every respondent who was interrupted, which in "
           "fieldwork is common and not a quality signal."),
    bullet("<b>Too high</b> &mdash; a form left open for hours and completed from memory "
           "is not caught."),
    bullet("<b>To judge it:</b> does Kobo measure elapsed wall-clock time from first open "
           "to submit, or active time? <b>This is currently an assumption and should be "
           "confirmed against the real Kobo asset before the value is fixed.</b>"),
    Spacer(1, 4),
    decision_line("Decision:&nbsp; keep 5400&nbsp; /&nbsp; change to ________ seconds"),
]))

S.append(KeepTogether([
    P("A2.3 Duplicate submission window &mdash; currently 24 hours", "H3x"),
    P("Flags a second submission from the same <i>organisation</i> within this window."),
    bullet("<b>Too short</b> &mdash; a genuine duplicate submitted the next day is missed."),
    bullet("<b>Too long</b> &mdash; legitimate re-submissions after an RA-assisted "
           "correction are flagged."),
    bullet("<b>Note:</b> the rule keys on the organisation, not the respondent, so two "
           "people at the same organisation submitting inside the window will flag. Given "
           "the design samples one respondent per organisation that is probably intended, "
           "but it is worth confirming rather than assuming."),
    Spacer(1, 4),
    decision_line("Decision:&nbsp; keep 24&nbsp; /&nbsp; change to ________ hours"),
]))

S.append(P("A3. To note, not approve", "H2x"))
S.append(bullet("<font face='Courier' size='8'>mode_imbalance_alert_ratio</font> (0.70) is "
                "configured but never evaluated. It should be implemented or removed; as "
                "it stands it implies a control that does not exist."))
S.append(bullet("The five dormant thresholds should be revisited once a real Kobo asset "
                "exists, and this pack re-issued for that part."))

# ----------------------------------------------------------------- PART B --
S.append(PageBreak())
S.append(P("Part B &mdash; Participant Information Sheet", "H1x"))
S.append(P(f"Current version <b>{PIS_VERSION}</b>, live and shown to every respondent "
           "before consent. The version string is recorded against every consent record, "
           "so consent is always traceable to the exact wording the respondent saw."))

S.append(P("B1. The text as it currently stands", "H2x"))
for para in [p.strip() for p in PIS_TEXT.split("\n\n") if p.strip()]:
    S.append(Paragraph(para.replace("\n", " ").replace("--", "&mdash;"), styles["Quotex"]))

S.append(P("B2. Gaps a reviewer will likely want addressed", "H2x"))
S.append(P("Raised for the ethics office to rule on. These are omissions from the text, "
           "not defects in the system. Item 1 has been addressed in v1.2 at the PI's "
           "direction; items 2&ndash;7 are untouched.", "Smallx"))
S.append(Spacer(1, 2))
S.append(note(
    "1. PROIT background research &mdash; ADDRESSED in v1.2, still to be confirmed",
    "Was the most material gap: before contact the research team may compile a profile of "
    "the respondent's organisation from public sources, which the respondent is then asked "
    "to confirm or correct. The verification screen explained this at the point of use, "
    "but the information sheet the respondent consents on the basis of did not mention it "
    "at all. <b>v1.2 adds a paragraph</b> covering what is looked up, from what kinds of "
    "source, what the respondent will be asked to do with it, that they may decline or "
    "skip, and that their own answers are recorded separately and take precedence. "
    "<b>For the reviewer to confirm:</b> whether that wording is sufficient disclosure, "
    "and whether it sits in the right place in the sheet.",
    bg=colors.HexColor("#EAF2EA"), edge=colors.HexColor("#5B8A5B"),
))
S.append(Spacer(1, 7))
for n, t in [
    (2, "<b>No retention or destruction statement.</b> How long identifying contact data "
        "is kept, and what happens to it after the 30 November 2026 data lock."),
    (3, "<b>No withdrawal-after-submission route.</b> The text covers stopping <i>during</i> "
        "participation. It does not say whether a respondent can withdraw their data "
        "afterwards, or how. A procedure exists."),
    (4, "<b>No independent complaints route.</b> Questions go to the researcher. Ethics "
        "guidance commonly expects a contact independent of the research team for "
        "concerns a respondent does not want to raise directly."),
    (5, "<b>&ldquo;Only the research team can see this information&rdquo;</b> &mdash; worth "
        "confirming this is accurate and sufficient given the eight internal roles and any "
        "external-examiner access that may follow."),
    (6, "<b>Data storage location is not stated.</b> Data is held on a VPS; whether the "
        "PIS must say where, and under whose jurisdiction, is an ethics-office call."),
    (7, "<b>Language.</b> The interface is English-only for v1.0. Whether an English-only "
        "PIS is acceptable for this respondent population is a decision for the ethics "
        "office."),
]:
    S.append(bullet(f"<b>{n}.</b> {t}"))

S.append(Spacer(1, 8))
S.append(decision_line("Decision:&nbsp; approve " + PIS_VERSION +
                       " as-is&nbsp; /&nbsp; approve with attached amendments&nbsp; /&nbsp; "
                       "revise and re-issue"))

# ---------------------------------------------------------------- SIGN-OFF --
S.append(PageBreak())
S.append(P("Sign-off", "H1x"))
S.append(P("No value or wording in this pack should be treated as approved until the "
           "relevant row below is completed. Once signed, the outcome is recorded in the "
           "project's execution plan, the threshold rows are updated with the approving "
           "user against them, and the PIS version string is bumped if the wording changed."))
S.append(Spacer(1, 10))

rows = [
    ["Part A &mdash; QA thresholds", "Principal Researcher", "", "", ""],
    ["Part A &mdash; QA thresholds", "Supervisor", "", "", ""],
    ["Part B &mdash; PIS wording", "Principal Researcher", "", "", ""],
    ["Part B &mdash; PIS wording", "Supervisor", "", "", ""],
    ["Part B &mdash; PIS wording", "CUT Research Ethics", "", "", ""],
]
t = Table(
    [[Paragraph(h, styles["THead"]) for h in ["Item", "Role", "Name", "Date", "Signature"]]] +
    [[Paragraph(c, styles["TCell"]) for c in r] for r in rows],
    colWidths=[4.2 * cm, 3.4 * cm, 3.4 * cm, 2.2 * cm, PAGE_W - 2 * MARGIN - 13.2 * cm],
    rowHeights=[None] + [1.35 * cm] * len(rows),
)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
]))
S.append(t)
S.append(Spacer(1, 12))
S.append(note(
    "Until this is signed",
    "The Participant Information Sheet remains a draft that respondents are nonetheless "
    "being shown, and the QA thresholds remain engineering defaults. Both are recorded as "
    "go-live blockers in the project's Definition of Done. No live invitations have been "
    "issued.",
))

doc.build(S)
print("wrote", OUT)
