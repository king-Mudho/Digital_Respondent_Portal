# -*- coding: utf-8 -*-
"""
Builds the ABF-FST Digital Respondent Portal complete user guide as a PDF.
Standalone script -- no Django app context needed, only reportlab (already
a backend dependency, `backend/requirements/base.txt`). Run from the repo
root with the backend's own venv:
    backend/.venv/Scripts/python.exe docs/tools/build_guide.py
Writes the PDF next to this script (docs/tools/), regardless of the
working directory it's run from -- gitignored (docs/tools/*.pdf), not a
tracked file. Re-run and re-send this file any time role/contact/screen
details in this guide change; keep this script itself as the source of
truth, not the PDF.
"""

import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    PageBreak, NextPageTemplate, FrameBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ABF-FST_Digital_Respondent_Portal_User_Guide.pdf")

# Bump this whenever the guide's content changes, so a printed or emailed
# copy can be told apart from an earlier one. Deliberately not today's date
# at build time: rebuilding an unchanged guide should not look like a new
# revision.
REVISION = "Revision 3 &mdash; 13 September 2026"
REVISION_NOTE = (
    "Updated for role-scoped navigation (each role now sees only its own modules), "
    "the QA Dashboard, register search and paging, the PROIT pre-interview profile, "
    "and the eligibility and consent gates on the respondent flow. Organisations, "
    "sample cases and Main&ndash;Reserve pairing are all now handled from the Research "
    "Operations Centre rather than Django admin (Sections 4, 5.7 and 8), and the "
    "register figures throughout match the live system as at 13 September 2026. "
    "Supersedes Revision 2 of the same date."
)

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

styles.add(ParagraphStyle(
    name="CoverTitle", fontName="Helvetica-Bold", fontSize=27, leading=33,
    textColor=NAVY_DARK, alignment=TA_LEFT, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="CoverSub", fontName="Helvetica", fontSize=13.5, leading=19,
    textColor=MUTED, alignment=TA_LEFT, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="CoverMeta", fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="Eyebrow", fontName="Helvetica-Bold", fontSize=9.5, leading=12,
    textColor=GOLD, spaceAfter=2, tracking=1,
))
styles.add(ParagraphStyle(
    name="H1", fontName="Helvetica-Bold", fontSize=19, leading=23,
    textColor=NAVY_DARK, spaceBefore=4, spaceAfter=12,
))
styles.add(ParagraphStyle(
    name="H2", fontName="Helvetica-Bold", fontSize=13.5, leading=17,
    textColor=NAVY, spaceBefore=16, spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="H3", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    textColor=INK, spaceBefore=10, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Body", fontName="Helvetica", fontSize=10, leading=14.5,
    textColor=INK, spaceAfter=7, alignment=TA_LEFT,
))
styles.add(ParagraphStyle(
    name="BodySmall", fontName="Helvetica", fontSize=9, leading=13,
    textColor=MUTED, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="MyBullet", fontName="Helvetica", fontSize=10, leading=14.5,
    textColor=INK, spaceAfter=4, leftIndent=14, bulletIndent=2,
))
styles.add(ParagraphStyle(
    name="StepNum", fontName="Helvetica-Bold", fontSize=13, leading=16,
    textColor=GOLD,
))
styles.add(ParagraphStyle(
    name="StepTitle", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="StepBody", fontName="Helvetica", fontSize=9.5, leading=13.5,
    textColor=MUTED,
))
styles.add(ParagraphStyle(
    name="TableHead", fontName="Helvetica-Bold", fontSize=8.7, leading=11,
    textColor=WHITE,
))
styles.add(ParagraphStyle(
    name="TableCell", fontName="Helvetica", fontSize=9, leading=12.5,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableCellBold", fontName="Helvetica-Bold", fontSize=9, leading=12.5,
    textColor=NAVY_DARK,
))
styles.add(ParagraphStyle(
    name="CodeInline", fontName="Courier", fontSize=8.7, leading=12.5,
    textColor=NAVY_DARK, backColor=WASH,
))
styles.add(ParagraphStyle(
    name="WarnTitle", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
    textColor=colors.HexColor("#7A5410"),
))
styles.add(ParagraphStyle(
    name="WarnBody", fontName="Helvetica", fontSize=9.3, leading=13,
    textColor=colors.HexColor("#5C4008"),
))
styles.add(ParagraphStyle(
    name="TOCHeading1", fontName="Helvetica-Bold", fontSize=11.5, leading=18,
    textColor=NAVY_DARK, spaceBefore=8,
))
styles.add(ParagraphStyle(
    name="TOCHeading2", fontName="Helvetica", fontSize=10, leading=15,
    textColor=INK, leftIndent=14,
))
styles.add(ParagraphStyle(
    name="Footer", fontName="Helvetica", fontSize=8, textColor=MUTED,
))


def P(text, style="Body"):
    return Paragraph(text, styles[style])


def note(title, body):
    t = Table(
        [[P("<b>" + title + "</b>", "WarnTitle")], [P(body, "WarnBody")]],
        colWidths=[PAGE_W - 2 * MARGIN],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, WARN_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 8),
    ]))
    return t


def data_table(head, rows, col_widths, head_bg=NAVY):
    body = [[P(h, "TableHead") for h in head]]
    for r in rows:
        body.append([P(c, "TableCell") for c in r])
    t = Table(body, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), head_bg),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(body)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), WASH))
    t.setStyle(TableStyle(style))
    return t


def step_row(number, title, body, tag=None):
    title_html = f"{title}"
    if tag:
        title_html += f'  <font color="#A23B2E" size="7.5"> [{tag}]</font>'
    cell = [P(str(number), "StepNum"), Spacer(1, 0)]
    row = Table(
        [[cell[0], [P(title_html, "StepTitle"), Spacer(1, 2), P(body, "StepBody")]]],
        colWidths=[1.1 * cm, PAGE_W - 2 * MARGIN - 1.1 * cm],
    )
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
    ]))
    return row


def h1(text, key=None):
    p = Paragraph(text, styles["H1"])
    if key:
        p._bookmarkName = key
    return p


def h2(text):
    return Paragraph(text, styles["H2"])


def h3(text):
    return Paragraph(text, styles["H3"])


class GuideDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            text = flowable.getPlainText()
            if style_name == "H1":
                self.notify("TOCEntry", (0, text, self.page))
                key = getattr(flowable, "_bookmarkName", None) or f"h1-{text}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=0, closed=False)
            elif style_name == "H2":
                self.notify("TOCEntry", (1, text, self.page))


def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY_DARK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, PAGE_H - 0.55 * cm, PAGE_W, 0.55 * cm, fill=1, stroke=0)
    canvas.restoreState()


def plain_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, PAGE_H - 1.55 * cm, PAGE_W - MARGIN, PAGE_H - 1.55 * cm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(MARGIN, PAGE_H - 1.35 * cm, "ABF-FST DIGITAL RESPONDENT PORTAL")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.35 * cm, "Complete User Guide")
    canvas.line(MARGIN, 1.35 * cm, PAGE_W - MARGIN, 1.35 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 1.05 * cm, "Chinhoyi University of Technology · ABF-FST doctoral study")
    canvas.drawRightString(PAGE_W - MARGIN, 1.05 * cm, f"Page {doc.page - 1}")
    canvas.restoreState()


doc = GuideDoc(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
               topMargin=MARGIN, bottomMargin=MARGIN)

cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")
body_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="body")

doc.addPageTemplates([
    PageTemplate(id="Cover", frames=[cover_frame], onPage=cover_page),
    PageTemplate(id="Body", frames=[body_frame], onPage=plain_page),
])

toc = TableOfContents()
toc.levelStyles = [styles["TOCHeading1"], styles["TOCHeading2"]]

story = []

# --------------------------------------------------------------- COVER ----
story.append(NextPageTemplate("Body"))
cover_style_title = ParagraphStyle("CT", parent=styles["CoverTitle"], textColor=WHITE, fontSize=30, leading=36)
cover_style_sub = ParagraphStyle("CS", parent=styles["CoverSub"], textColor=colors.HexColor("#C9D3DC"))
cover_style_meta = ParagraphStyle("CM", parent=styles["CoverMeta"], textColor=colors.HexColor("#8FA0AF"))
cover_style_eyebrow = ParagraphStyle("CE", parent=styles["Eyebrow"], textColor=GOLD)

story.append(Spacer(1, 6.5 * cm))
story.append(Paragraph("COMPLETE USER GUIDE", cover_style_eyebrow))
story.append(Spacer(1, 6))
story.append(Paragraph("ABF-FST Digital<br/>Respondent Portal", cover_style_title))
story.append(Spacer(1, 14))
story.append(Paragraph(
    "From first login to a completed questionnaire &mdash; how Administrators, "
    "Field Coordinators, Research Assistants and respondents each use the system.",
    cover_style_sub,
))
story.append(Spacer(1, 40))
meta_table = Table(
    [
        [Paragraph("STUDY", ParagraphStyle("m", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph("Developing and Validating the Agribusiness Bankability Framework for Food\nSystems Transformation through Novel Financing Models in Zimbabwe", cover_style_meta)],
        [Paragraph("PRINCIPAL RESEARCHER", ParagraphStyle("m2", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph("Happyson Saina &mdash; Doctor of Strategic Management candidate,\nChinhoyi University of Technology", cover_style_meta)],
        [Paragraph("CONTACT", ParagraphStyle("m4", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph("0773943709 &nbsp;&middot;&nbsp; abffst.research.cut@gmail.com", cover_style_meta)],
        [Paragraph("LIVE AT", ParagraphStyle("m3", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph("research.agribizframework.com", cover_style_meta)],
        [Paragraph("REVISION", ParagraphStyle("m5", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph(REVISION, cover_style_meta)],
    ],
    colWidths=[3.6 * cm, PAGE_W - 2 * MARGIN - 3.6 * cm],
)
meta_table.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#33475C")),
    ("LINEABOVE", (0, 1), (-1, 1), 0.5, colors.HexColor("#33475C")),
    ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.HexColor("#33475C")),
    ("LINEABOVE", (0, 3), (-1, 3), 0.5, colors.HexColor("#33475C")),
    ("LINEABOVE", (0, 4), (-1, 4), 0.5, colors.HexColor("#33475C")),
    ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#33475C")),
    ("LEFTPADDING", (0, 0), (0, -1), 0),
]))
story.append(meta_table)

story.append(PageBreak())

# ----------------------------------------------------------------- TOC ----
story.append(Paragraph("Contents", styles["H1"]))
story.append(toc)
story.append(PageBreak())

# ------------------------------------------------------------ SECTION 1 ---
story.append(h1("1. Introduction", key="intro"))
story.append(note("What changed in this revision", REVISION_NOTE))
story.append(Spacer(1, 8))
story.append(P(
    "The ABF-FST Digital Respondent Portal is the research-operations platform for a "
    "doctoral study on agribusiness financing readiness in Zimbabwe. It authenticates and "
    "routes selected respondent organisations, captures consent and eligibility, launches "
    "the KoboToolbox questionnaire, reconciles submissions, and runs the Key Informant "
    "Interview (KII), documentary-evidence, contact/CRM, quality-assurance and "
    "fieldwork-cost operations behind the study's 400-organisation quantitative sample."
))
story.append(P(
    "It is <b>not</b> a public survey tool. Nobody can browse into it &mdash; every "
    "respondent visit starts from a personal, single-use invitation link issued by a "
    "Field Coordinator or Admin. It also never calculates or shows any score, rating, or "
    "financing decision to a respondent, at any point."
))
story.append(h2("1.1 The two sides of the system"))
story.append(P(
    "<b>The Research Operations Centre</b> (everything under <font face='Courier'>/admin</font>) "
    "&mdash; the internal side, used by the PI, Field Coordinators and Research Assistants "
    "to manage the sample, send invitations, review submissions, log KIIs and documentary "
    "evidence, and export data."
))
story.append(P(
    "<b>The respondent-facing flow</b> (every link under <font face='Courier'>/i/&lt;token&gt;</font>) "
    "&mdash; the public side, opened only via a personal invitation link, walking a "
    "respondent from organisation confirmation through consent to the actual questionnaire."
))
story.append(h2("1.2 Key ideas worth knowing before you start"))
kv_rows = [
    ["Master ID / Sample ID", "Every organisation gets a system-generated Master ID "
     "(e.g. MID-HA-000005); every sample slot gets a Sample ID (e.g. SID-2026-000005). "
     "Both are assigned automatically and never reused, even if the record is later deleted."],
    ["Main-400 / Reserve-400", "The study samples 400 primary (“Main”) organisations, "
     "each matched to one locked “Reserve” organisation that can only be activated "
     "as a replacement for a documented reason (ineligible, inactive, duplicate, refusal, "
     "or nonresponse exhausted)."],
    ["Workflow status (S00–S16)", "Every Main sample case moves through a fixed "
     "sequence — Selected, Verification required, Organisation verified, Eligible "
     "respondent identified, Invitation prepared/sent/opened, Survey started/submitted, "
     "QA query/passed, Completed — or one of several “drop” states (Refused, "
     "Nonresponse, Ineligible, Duplicate/Inactive) that make its Reserve match eligible "
     "for activation."],
    ["Invitation token", "A single-use, personal link (or an 8-character manual code for "
     "phone administration). Only its salted hash is ever stored — the raw link/code "
     "is shown to whoever issues it exactly once, and never again."],
]
story.append(data_table(["Term", "What it means"], kv_rows, [4.4 * cm, PAGE_W - 2 * MARGIN - 4.4 * cm]))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 2 ---
story.append(h1("2. Getting Started", key="getting-started"))
story.append(h2("2.1 Where to sign in"))
story.append(data_table(
    ["Environment", "Address"],
    [["Production (live)", "research.agribizframework.com/admin/login"],
     ["Local development", "localhost:3000/admin/login"]],
    [4.5 * cm, PAGE_W - 2 * MARGIN - 4.5 * cm],
))
story.append(Spacer(1, 6))
story.append(P(
    "There is one login screen for every internal role &mdash; what you see afterward "
    "depends on your account's role (Section 3). There is no self-service sign-up: every "
    "account is created for you by the PI/Admin."
))
story.append(h2("2.2 Signing in"))
story.append(P(
    "Open the address above, enter your username and password, and you land on "
    "<b>your role's own first screen</b> — not a shared home page. A Contact RA lands on "
    "the Main-400 Register, a QUAN QA RA on the QA Dashboard, a KII or Documentary RA on "
    "the KII/Document Dashboard, and the PI, Field Coordinator, Analyst and Supervisor on "
    "the Executive Dashboard. Section 3 lists each role's landing screen."
))
story.append(Spacer(1, 4))
story.append(note(
    "“Too many sign-in attempts from this network”",
    "Not a password problem. Sign-in is rate-limited per network address, and a whole "
    "team working from one office connection shares that address. Wait about a minute and "
    "try again. A genuinely wrong password says so explicitly instead."
))
story.append(h2("2.3 Finding your way around"))
story.append(P(
    "The top navigation bar lists <b>only the screens your role can open</b> — it is not "
    "a full menu with some items disabled. A Contact RA sees two entries; the PI sees "
    "fifteen. If you open a link to a screen outside your role (someone shares a URL, or "
    "you have an old bookmark) you get a short “This screen isn't part of your role” "
    "card with a link back to your own start screen, rather than a page that fails as it "
    "loads."
))
story.append(P(
    "Every screen except your landing screen shows a <b>&lt;- Back to &hellip;</b> link at "
    "the top, pointing at its logical parent — a case detail page back to the register it "
    "came from, a sub-dashboard back to the Executive Dashboard. Where that parent is a "
    "screen your role cannot open, the link points at your own start screen instead."
))
story.append(P(
    "<b>Change password</b>, next to “Sign out” (top right), lets you set your own "
    "password at any time — no need to ask the PI/Admin unless you've forgotten it "
    "entirely. Both are available to every role. Use “Sign out” when you're done, "
    "especially on a shared device."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 3 ---
story.append(h1("3. Roles &mdash; Who Can Do What", key="roles"))
story.append(P(
    "Every internal account has exactly one role, and that role decides <b>which screens "
    "appear in your navigation bar at all</b>. You are not shown a full menu with items "
    "you cannot use; you are shown your own modules and nothing else. Permissions are "
    "then enforced again by the server on every action, so a screen reached another way "
    "(a shared URL, an old bookmark) still refuses the underlying request."
))
story.append(h2("3.1 What each role sees in the navigation bar"))
nav_rows = [
    ["PI / Admin", "15", "Everything, including the <b>Audit Log</b> and both exports.",
     "Executive Dashboard"],
    ["Field Coordinator", "14", "Everything except the Audit Log.", "Executive Dashboard"],
    ["Supervisor (read-only)", "13", "Everything except the Audit Log and Export — "
     "and read-only throughout.", "Executive Dashboard"],
    ["Analyst", "6", "Executive, Sampling, Contact and KII/Document dashboards; Cost; "
     "Export. Read-only.", "Executive Dashboard"],
    ["Contact RA", "2", "Main-400 Register; Appointments.", "Main-400 Register"],
    ["QUAN/Kobo QA RA", "2", "QA Dashboard; QA Queue.", "QA Dashboard"],
    ["KII RA", "2", "KII/Document Dashboard; KII Register.", "KII/Document Dashboard"],
    ["Documentary RA", "2", "KII/Document Dashboard; Documents.", "KII/Document Dashboard"],
]
story.append(data_table(
    ["Role", "Screens", "Modules in the navigation bar", "Lands on"],
    nav_rows,
    [3.1 * cm, 1.5 * cm, PAGE_W - 2 * MARGIN - 9.2 * cm, 4.6 * cm],
))
story.append(Spacer(1, 4))
story.append(P(
    "<b>Change password</b> and <b>Sign out</b> are available to every role and sit "
    "outside this list.", "BodySmall"
))

story.append(h2("3.2 What each role can do"))
role_rows = [
    ["PI / Admin", "Every screen and action, the Audit Log, both data exports "
     "(de-identified and full operational), plus Django's own admin site for the handful "
     "of edge cases the Research Operations Centre doesn't cover yet (Section 4)."],
    ["Field Coordinator", "Registering organisations/sample cases, sample register &amp; "
     "case detail, workflow transitions, reserve activation, sending/revoking "
     "invitations, logging contact attempts, appointments, cost entries, triggering Kobo "
     "sync, the full KII/Documents/QA workflow, every aggregate dashboard and the "
     "de-identified export. Everything except the Audit Log and the operational "
     "(contact-identifying) export."],
    ["Contact RA", "Sample register &amp; case detail, logging contact attempts, "
     "appointment status, and sending/revoking invitations — but only for cases a Field "
     "Coordinator/Admin has <b>assigned</b> to them (Section 5.7). A case assigned to "
     "someone else, or not yet assigned to anyone, simply doesn't appear. No dashboards, "
     "no KII/Documents/QA, no cost logging, no reserve activation or workflow "
     "transitions, no Kobo sync trigger."],
    ["QUAN/Kobo QA RA", "The QA Dashboard, the QA queue and QA decisions, and the "
     "KoboToolbox sync trigger. <b>No</b> access to KII records or documents."],
    ["KII RA", "The KII register and KII detail — status transitions, participation and "
     "recording consent, transcript and coding progress — plus the KII/Document "
     "dashboard. <b>No</b> access to documents or QA decisions."],
    ["Documentary RA", "The documentary-evidence corpus and document detail — "
     "authenticity assessment, QA status, interpretive memo — plus the KII/Document "
     "dashboard. <b>No</b> access to KII records or QUAN QA decisions."],
    ["Analyst", "Every aggregate dashboard and the de-identified export. No write access "
     "anywhere."],
    ["Supervisor (read-only)", "Read-only visibility into everything an internal role can "
     "see — sample register &amp; case detail, contact events &amp; appointments, KII "
     "&amp; Documents &amp; QA queue, invitations, cost entries, and every aggregate "
     "dashboard. Cannot write anywhere, and — unlike Analyst — does not have the "
     "de-identified export."],
]
story.append(data_table(["Role", "Current access"], role_rows, [3.4 * cm, PAGE_W - 2 * MARGIN - 3.4 * cm]))
story.append(Spacer(1, 10))
story.append(note(
    "The three RA roles are separate, not interchangeable",
    "A KII RA cannot edit documentary evidence, a Documentary RA cannot take QUAN QA "
    "decisions, and a QUAN QA RA cannot touch either register. If someone needs to work "
    "across two of these, they need the Field Coordinator role — not a second account."
))
story.append(Spacer(1, 8))
story.append(note(
    "Read-only roles (Analyst, Supervisor)",
    "On screens that mix reading and writing — the Cost Dashboard also logs cost events, "
    "the KII register also creates records — these two roles see the figures and the "
    "lists but not the forms or buttons. Where it isn't obvious, a short “Read-only "
    "role” line says so in place of the controls."
))
story.append(Spacer(1, 8))
story.append(note(
    "Assigning a Contact RA to a case",
    "Only a Field Coordinator or Admin can assign (or reassign) which Contact RA owns a "
    "case — from the <b>Assigned Contact RA</b> dropdown on that case's detail page "
    "(Section 5.7). A Contact RA cannot assign cases to themselves or anyone else, and "
    "sees the current assignment as plain text rather than a dropdown."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 4 ---
story.append(h1("4. Setting Up Study Data (PI / Admin)", key="setup"))
story.append(note(
    "The three registers are already loaded",
    "The three approved registers were imported into the live system in September 2026 "
    "and are complete: <b>400 Main and 400 Reserve</b> sample cases across 800 "
    "organisations, with all 400 Main cases paired to their matched Reserve; <b>90 KII "
    "records</b> (Core-60 plus Reserve-30); and <b>100 documentary-evidence records</b>. "
    "This section is for organisations added <i>after</i> that &mdash; a replacement, a "
    "late addition, or a correction &mdash; not for setting the study up from scratch."
))
story.append(Spacer(1, 8))
story.append(P(
    "Registering an organisation and its sample case is done from the Research "
    "Operations Centre itself, at <b>Organisations</b> in the top navigation bar "
    "&mdash; no separate Django admin site needed for this. The screen is available to "
    "the PI and Field Coordinator."
))
story.append(P(
    "That now covers the whole job, Main&ndash;Reserve pairing included &mdash; Django "
    "admin is not needed for any part of setting up a case.", "BodySmall"
))
story.append(h2("4.1 The stratification fields"))
story.append(P(
    "The study's actual sampling design stratifies by <b>Province &times; Actor Family "
    "&times; Size Class</b> only. Entity type and value chain are free-text fields on "
    "the organisation record &mdash; useful descriptive detail, but not part of the "
    "stratum match. When you create a sample case for an organisation without picking a "
    "stratum yourself, the system resolves (or creates) the matching one automatically "
    "from that organisation's own province/actor family/size class."
))
story.append(h2("4.2 To register a Main organisation and its matched Reserve"))
steps_setup = [
    ("1", "Open <b>Organisations</b> in the top navigation bar."),
    ("2", "Fill in the New organisation form (name, district, province, entity type, "
          "actor family, value chain, size class) and click <b>Register organisation</b>. "
          "Its Master ID is generated the moment you save."),
    ("3", "The page offers to create that organisation's sample case immediately &mdash; "
          "pick <i>Main</i> or <i>Reserve</i> and click <b>Create sample case</b>, which "
          "takes you straight to the new case's detail page. You can also do this later "
          "from the organisation's row in the list below the form."),
    ("4", "Repeat steps 1&ndash;3 for the matched counterpart (Reserve for a Main "
          "organisation, or vice versa) &mdash; using the <i>same</i> province/actor "
          "family/size class, since that's what makes it a valid match for the same "
          "stratum."),
    ("5", "On the Main case's detail page, use <b>Assigned Contact RA</b> (Section 5.7) "
          "if a specific Research Assistant should handle it &mdash; a Contact RA sees "
          "only the cases assigned to them, so an unassigned case is invisible to them."),
    ("6", "Pair the two cases from the Main case's <b>Matched Reserve case</b> panel "
          "(Section 5.7). The dropdown lists only Reserve cases that are still locked and "
          "not already claimed by another Main, with same-stratum ones first. Without a "
          "pairing the Reserve exists but is not identified as this Main case's "
          "replacement."),
]
for num, text in steps_setup:
    story.append(step_row(num, "", text))
story.append(Spacer(1, 6))
story.append(P(
    "Master IDs and Sample IDs are always generated automatically — you never type one "
    "in. A Reserve case starts <b>LOCKED</b> and cannot receive an invitation until it "
    "is deliberately activated (Section 5.12)."
))
story.append(Spacer(1, 4))
story.append(h2("4.3 Finding an organisation you already registered"))
story.append(P(
    "The list below the form holds every registered organisation, 20 at a time, with a "
    "search box that matches name, Master ID or district, and Previous / Next controls at "
    "the foot. Each row has a <b>Create sample case</b> link if that organisation doesn't "
    "have one yet."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 5 ---
story.append(h1("5. The Research Operations Centre, Screen by Screen", key="screens"))
story.append(P(
    "Every screen below lives under the top navigation bar once signed in. You will only "
    "see the ones your role covers (Section 3.1) — this section describes all of them."
))

story.append(h2("5.1 Executive Dashboard"))
story.append(P("The home screen for the PI, Field Coordinator, Analyst and Supervisor. "
               "Overall progress against the 400 QUAN / 60 KII / 50–75 "
               "document targets, days remaining to the data-lock date, and the "
               "lowest-filled strata (where fieldwork attention is most needed). Quick "
               "links across the top open the sub-dashboards your role can reach."))
story.append(P(
    "These are <i>completion</i> targets, not how much is loaded. The registers "
    "deliberately hold more than the target &mdash; 90 KII records against a target of "
    "60 completed interviews, 100 documents against a 50&ndash;75 coded corpus &mdash; "
    "because the surplus is reserve depth for nonresponse, not extra work to finish.",
    "BodySmall",
))

story.append(h2("5.2 Sampling and Contact dashboards"))
story.append(P("<b>Sampling</b>: Main-400 counts by province and stratum, reserve "
               "activations by reason. <b>Contact</b>: organisations verified, eligible "
               "respondents identified, invitations sent/opened, appointments upcoming, "
               "refusals, unreachable cases."))

story.append(h2("5.3 QA Dashboard"))
story.append(P("The QUAN QA RA's landing screen, and available to the Field Coordinator, "
               "PI and Supervisor. Submissions received today and cumulatively, how many "
               "are waiting in the QA queue, how many QA decisions have been recorded, and "
               "the split by administration mode (self-administered, phone-assisted, "
               "WhatsApp-assisted and so on). <b>Refresh</b> re-reads the figures without "
               "reloading the page; <b>Open QA queue</b> goes straight to the submissions "
               "themselves."))

story.append(h2("5.4 KII / Document Dashboard"))
story.append(P("The KII RA's and Documentary RA's landing screen. KII and document counts "
               "against target, broken down by status, type and QA outcome. Counts only — "
               "the individual records live in the registers below."))

story.append(h2("5.5 Finding things: search and paging"))
story.append(P(
    "The registers hold real fieldwork volumes — 400 Main cases, 400 Reserve, 800 "
    "organisations, 90 KII records and 100 documents — and show 20 rows at a time. Every "
    "register (Main-400, Organisations, KII, Documents, Appointments, Reserve Activation, "
    "Audit Log) therefore has <b>Previous / Next</b> controls and a “Showing 21–40 of "
    "400” counter at the foot of the list."
))
story.append(P(
    "Most also have a <b>search box</b> above the list. Search matches the identifiers and "
    "names you would actually have to hand: Sample ID, Master ID or organisation name on "
    "the Main-400 Register; name, Master ID or district on Organisations; KII ID, "
    "participant name or role on the KII register; title, document ID or author on "
    "Documents. Searching always returns you to page 1."
))

story.append(h2("5.6 Main-400 Register"))
story.append(P("Every Main and Reserve sample case, with its Sample ID, Master ID, "
               "organisation and current status. The dropdown switches between the Main "
               "and Reserve registers. Click <b>View</b> to open a case's detail page. "
               "Roles that can also create cases get a <b>Register organisation</b> button "
               "here, since a case is always created from an organisation."))

story.append(h2("5.7 Sample Case Detail"))
story.append(P("The busiest screen in the system. From here you can:"))
story.append(Paragraph("&bull; <b>Assign a Contact RA</b> — pick which Contact RA owns "
               "this case from the dropdown (Field Coordinator/Admin only). That RA's "
               "own view of the Main-400 Register and this case is then scoped to only "
               "the cases assigned to them — an unassigned case, or one assigned to "
               "someone else, simply doesn't appear for other Contact RAs.", styles["MyBullet"]))
story.append(Paragraph("&bull; <b>Send an invitation</b> — pick a channel (WhatsApp, "
               "Email, SMS, Printed code, QR) and a wave number, then click Send. The "
               "link and manual code are shown <i>once</i> — copy them immediately "
               "into the message you send (see Section 6). Every prior invitation for the "
               "case is listed below, with a Revoke button on any still-open one.", styles["MyBullet"]))
story.append(Paragraph("&bull; <b>Advance the workflow status</b> — buttons show only "
               "the transitions the S00–S16 state machine actually allows from the "
               "case's current status.", styles["MyBullet"]))
story.append(Paragraph("&bull; <b>Log a contact attempt</b> — channel, outcome and an "
               "optional note, added to the case's contact timeline.", styles["MyBullet"]))
story.append(Paragraph("&bull; <b>Set the matched Reserve case</b> — which Reserve "
               "replaces this Main case if it drops out (Field Coordinator/Admin only, "
               "and only on Main cases). The dropdown offers only Reserve cases that are "
               "still locked and not already claimed by another Main, listing "
               "same-stratum ones first; picking one from a different stratum is allowed "
               "but flagged on screen and in the audit log, since it weakens the "
               "stratified design. Everyone else sees the current pairing as plain "
               "text.", styles["MyBullet"]))
story.append(Paragraph("&bull; <b>Build a pre-interview profile (PROIT)</b> — see "
               "Section 5.16.", styles["MyBullet"]))

story.append(h2("5.8 Appointment Queue"))
story.append(P("Every appointment a respondent has requested (phone call, WhatsApp-assisted "
               "session, etc.). Each row identifies the case — Sample ID and organisation "
               "name, or the KII ID for an informant appointment — so you can tell whose "
               "appointment it is at a glance. Status buttons (Confirmed, Completed, "
               "Missed, Cancelled) are restricted to whatever transition is valid from the "
               "current status; a row that has reached a final status says “No further "
               "action” rather than showing an empty space. The status dropdown above the "
               "list filters the queue."))

story.append(h2("5.9 QA Queue"))
story.append(P("Every QUAN submission awaiting a human decision: Accept, Re-query, or "
               "Reject. <b>A note is required</b> — the buttons stay disabled until you "
               "write one, because the server refuses a decision without it. At the top, "
               "the <b>KoboToolbox sync</b> panel shows when data last pulled from Kobo "
               "and lets you trigger a pull on demand (“Sync now”) instead of waiting "
               "for the next scheduled run."))

story.append(h2("5.10 KII Register"))
story.append(P("The list of Key Informant Interview records, a button to create a new one, "
               "and a detail page per record for: advancing its status (Invited -&gt; "
               "Scheduled -&gt; Completed/Declined/No-show), recording participation and "
               "recording consent as two <i>separate</i> decisions, and tracking transcript "
               "and coding progress. A KII cannot be marked Completed with a recording "
               "unless recording consent was captured first — this is enforced by the "
               "system, not just a reminder."))

story.append(h2("5.11 Documents"))
story.append(P("The documentary-evidence corpus, a button to add a new record, and a "
               "detail page per document for: assessing authenticity (Verified/Disputed), "
               "setting QA status (Included/Excluded), and writing an interpretive memo. "
               "A document cannot be marked Included until its authenticity has been "
               "assessed — the <b>Include</b> button stays disabled until then, and the "
               "server refuses it independently."))

story.append(h2("5.12 Reserve Activation"))
story.append(P("Every currently-LOCKED Reserve case. Activating one always requires picking "
               "one of five authorised reasons (Ineligible, Inactive, Duplicate, Refusal, "
               "Nonresponse exhausted) and writing an evidence note — there is "
               "deliberately no free-text “other” option. Once activated, the "
               "case can receive its own invitation."))

story.append(h2("5.13 Cost Dashboard"))
story.append(P("Total fieldwork spend, cost per QA-passed QUAN submission, cost per "
               "completed KII, a breakdown by category, and a form to log a new cost "
               "event (date, category, amount). Read-only roles see the figures without "
               "the logging form."))

story.append(h2("5.14 Audit Log"))
story.append(P("Every sensitive action ever taken in the system — consent recorded, "
               "invitation issued/revoked, reserve activated, workflow transition "
               "(including rejected attempts), KII/document status changes, QA decisions "
               "— each correctly attributed to the signed-in user who performed it. "
               "PI/Admin only."))

story.append(h2("5.15 Data Export"))
story.append(P("Two CSV downloads, deliberately different in shape. The "
               "<b>de-identified analysis export</b> has no name, phone, email or "
               "gatekeeper field — safe to share with the wider research team. The "
               "<b>full operational export</b> includes contact details and is "
               "PI/Admin-only, for internal fieldwork use, never distributed externally — "
               "it isn't shown at all to anyone else."))

story.append(h2("5.16 PROIT &mdash; the pre-interview profile"))
story.append(P(
    "PROIT (Pre-Interview Respondent &amp; Organisation Intelligence and Verification "
    "Tool) shortens the interview by checking publicly available background facts "
    "<i>before</i> you speak to anyone, so the respondent confirms or corrects what you "
    "already have instead of answering from zero."
))
story.append(P(
    "It appears as a <b>pre-profile panel</b> on both the sample case detail page and the "
    "KII detail page. A researcher records each background fact with its source, the date, "
    "a locator, and a confidence rating (High / Moderate / Low), drawing on a four-tier "
    "source hierarchy — statutory registers first, then official reports, then reputable "
    "media, then corroborated public content. A second researcher reviews and "
    "<b>locks</b> the profile before the respondent is contacted."
))
story.append(P(
    "Three values are kept permanently separate and never merged: what the documents said, "
    "what the respondent themselves answered, and the researcher's reconciled value. On "
    "the KII side, an <b>adaptive gap engine</b> then generates interview questions only "
    "for what is still genuinely unresolved."
))
story.append(Spacer(1, 6))
story.append(note(
    "What PROIT may never do",
    "It can never pre-fill, skip or infer any frozen ABI / NFM / Digital-Readiness / FST "
    "scale item. It applies only to non-core descriptive background — organisation type, "
    "province, value chain, licences, publicly disclosed finance facilities and the like."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 6 ---
story.append(h1("6. Inviting a Respondent", key="inviting"))
story.append(h2("6.1 Issuing the invitation"))
steps_invite = [
    ("1", "Open the sample case's detail page (Main-400 Register -&gt; View)."),
    ("2", "In the Invitations panel, choose a channel and wave number, then click "
          "<b>Send Invitation</b>."),
    ("3", "Copy the link <i>and</i> the manual code shown — this is the only time "
          "they are ever displayed. If you navigate away without copying them, you must "
          "issue a new invitation to get a new link (the old one still works until you do)."),
]
for num, text in steps_invite:
    story.append(step_row(num, "", text))
story.append(Spacer(1, 8))
story.append(h2("6.2 What to actually send"))
story.append(P(
    "The panel gives you a raw link and code — it does not compose a message. Ready-"
    "to-use WhatsApp, email and manual-code templates are in "
    "<font face='Courier'>docs/29_RESPONDENT_GUIDE_AND_MESSAGING.md</font> in the project "
    "repository (also published as the <i>Field Invitation Protocol</i> reference page). "
    "Fill in the organisation name, contact name, the link, the expiry date, and your own "
    "contact details before sending."
))
story.append(h2("6.3 Administering different modes"))
mode_rows = [
    ["01", "Web self-administration", "Send the link; the respondent completes it unassisted."],
    ["02", "WhatsApp link, self-completion", "Send the link specifically via WhatsApp."],
    ["03", "Telephone interviewer-administered", "Call the respondent; walk through eligibility, information and consent verbally, then complete the form on their behalf."],
    ["04", "WhatsApp call, interviewer-assisted", "Same as phone-assisted, over a WhatsApp voice/video call."],
    ["05", "Video call, interviewer-assisted", "Same, over Teams / Zoom / Meet."],
    ["06", "Face to face", "In person; you operate the device while the respondent answers."],
]
story.append(data_table(["Code", "Mode", "What you do"], mode_rows, [1.6 * cm, 5.4 * cm, PAGE_W - 2 * MARGIN - 7 * cm]))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 7 ---
story.append(h1("7. The Respondent's Experience", key="respondent"))
story.append(P("What happens on the other end of the link — useful for briefing a "
               "respondent by phone, or simply to know what you're sending them into."))
resp_steps = [
    ("1", "Opens the link", "Any phone or computer, no app to install, no account to create.", None),
    ("2", "Confirms the organisation", "“Is this [Organisation Name]?” — a single tap.", None),
    ("3", "States their role", "Picks from a fixed list. If none fit, they see a thank-you message and the questionnaire never opens — ask them to nominate the right person instead.", "GATE"),
    ("4", "Reads the study information", "Purpose, confidentiality, and their rights, in a short mobile-readable page. They can go back from here.", None),
    ("5", "Gives consent", "An explicit “I agree to take part” action — never a pre-ticked box. They may decline at any point, and can re-read the information sheet first.", "GATE"),
    ("6", "Confirms background facts (PROIT)", "Only if a locked pre-profile exists for their case — otherwise this step is skipped entirely and they never see it. Each fact can be confirmed, corrected, or marked unknown / prefer not to say / not applicable. The whole step can also be skipped.", None),
    ("7", "Chooses how to answer", "Themselves right now, or a phone-assisted / WhatsApp-assisted / scheduled session instead.", None),
    ("8a", "Answers the questionnaire", "Opens the KoboToolbox form directly. If it can't open, they get a plain-language explanation, a Try again button, and the option to ask for researcher help instead — never a dead end.", None),
    ("8b", "Or requests a researcher call", "Picks a date and time — which must be in the future — and is told a researcher will be in touch. This route is only open once consent has been given.", "GATE"),
    ("9", "Done", "A neutral closing screen. Someone who completed the questionnaire is thanked for participating; someone who booked a call is told their request has been sent and a researcher will follow up — the two are deliberately worded differently. No score, rating, or financing decision is ever calculated or shown.", None),
]
for num, title, body, tag in resp_steps:
    story.append(step_row(num, title, body, tag))
story.append(Spacer(1, 10))
story.append(note(
    "If a respondent doesn't fit any role on the list",
    "This is the intended outcome for someone who isn't a knowledgeable organisational "
    "respondent — no answers are recorded from them, and <i>Respondent.is_eligible</i> "
    "stays false. Ask them to nominate the correct person at that organisation, then issue "
    "that person their own, separate invitation. The questionnaire stays closed to that "
    "case until an eligible respondent has actually been recorded — the system enforces "
    "this itself, not just by hiding the next screen."
))
story.append(Spacer(1, 8))
story.append(note(
    "If something goes wrong mid-flow",
    "Every step now reports failure in plain language — an expired or revoked link, a "
    "busy connection, a lost signal — and leaves the respondent able to try again. If a "
    "respondent tells you “I pressed the button and nothing happened”, ask what the "
    "screen said: there should always be a message."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 8 ---
story.append(h1("8. A Complete Walkthrough", key="walkthrough"))
story.append(P(
    "Start to finish, for one organisation &mdash; and who does each part. Steps 1 and 2 "
    "are already done for every organisation in the imported registers; they apply to an "
    "organisation added afterwards."
))
walk_steps = [
    ("1", "<b>PI / Field Coordinator</b> registers the organisation at <b>Organisations</b> "
          "in the navigation bar, and creates its sample case from the same screen "
          "(Section 4). Master ID and Sample ID are generated automatically."),
    ("2", "<b>PI / Field Coordinator</b> assigns a Contact RA on the case detail page, if a "
          "specific RA should own it — until then, no Contact RA can see the case."),
    ("3", "<b>Field Coordinator / Contact RA</b> advances the workflow status through "
          "verification (S01 -&gt; S02 -&gt; S03) as the organisation and an eligible "
          "respondent are confirmed."),
    ("4", "<b>Optionally</b>, a researcher builds and locks a PROIT pre-profile for the "
          "case (Section 5.16), so the respondent confirms background facts instead of "
          "answering them from scratch."),
    ("5", "<b>Field Coordinator / Contact RA</b> sends the invitation from the case detail "
          "page, copies the link and manual code immediately (shown once), and sends them "
          "using one of the message templates. The workflow status advances to Invitation "
          "sent (S05) automatically."),
    ("6", "<b>The respondent</b> opens the link, confirms the organisation, states their "
          "role, reads the information sheet and consents. They then either complete the "
          "questionnaire themselves or request an assisted session — logged as an "
          "Appointment, which requires consent first."),
    ("7", "<b>Contact RA</b> works the Appointment Queue for anyone who asked to be "
          "called, confirming and then completing each appointment."),
    ("8", "On submission, the scheduled Kobo reconciliation job (or a manual “Sync now” "
          "from the QA queue) pulls the response in."),
    ("9", "<b>QUAN/Kobo QA RA</b> reviews the submission on the QA queue and records "
          "Accept, Re-query, or Reject — each with a mandatory note."),
    ("10", "Once QA-passed, the submission counts toward the Executive Dashboard's "
           "progress figures and the QA Dashboard's totals."),
    ("11", "If the case falls through (refusal, ineligible, nonresponse exhausted), "
           "<b>PI / Field Coordinator</b> activates its matched Reserve with a reason and "
           "evidence note (Section 5.12), and that Reserve then starts at step 3."),
    ("12", "At data lock, <b>PI/Admin</b> runs the de-identified analysis export for the "
           "wider research team, and the full operational export for internal records."),
]
for num, text in walk_steps:
    story.append(step_row(num, "", text))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 9 ---
story.append(h1("9. Troubleshooting", key="troubleshooting"))
story.append(h2("9.1 Respondents"))
trouble_rows = [
    ["“The link says it's not valid.”", "Typo, or the link expired / was revoked / was superseded by a newer one.", "Open the case's detail page and send a new invitation — it issues a fresh link and invalidates the old one."],
    ["“I already did this.”", "Already completed, or a new wave was issued since.", "Check the Invitations history on the case detail page for the current status before re-issuing."],
    ["“I'm not the right person to answer this.”", "Doesn't fit any listed role category.", "The intended ineligible path — no answers are recorded. Ask them to nominate the right person and issue them their own invitation."],
    ["“It won't let me pick a time.”", "The appointment date/time chosen is in the past.", "Times must be in the future. The picker blocks earlier ones and the server refuses them."],
    ["“It says it couldn't confirm my role.”", "Consent was recorded but no eligible respondent exists for that case.", "Have them complete the role question, or record the eligible respondent from the case detail page before they retry."],
    ["“Will my financing be affected by my answers?”", "Reasonable concern given the study's subject.", "No — no score, rating, or financing decision is ever generated or shown, at any point."],
]
story.append(data_table(["Situation", "Likely cause", "What to do"], trouble_rows,
                         [4.6 * cm, 4.6 * cm, PAGE_W - 2 * MARGIN - 9.2 * cm]))

story.append(Spacer(1, 12))
story.append(h2("9.2 Internal users"))
trouble_rows_internal = [
    ["“This screen isn't part of your role.”", "You opened a screen outside your role — usually a shared link or an old bookmark.", "Use the link on that card to return to your own start screen. If you should have access, ask the PI to change your role (Section 3)."],
    ["A module is missing from my navigation bar.", "Not a fault — the bar shows only your role's modules.", "Check Section 3.1 for what your role should see. Anything absent there is deliberate."],
    ["“Too many sign-in attempts from this network.”", "Sign-in is rate-limited per network address, shared by everyone in one office.", "Wait about a minute and try again. This is not a password error — a wrong password says so explicitly."],
    ["A QA decision button won't click.", "QA decisions require a note.", "Write the note first; the buttons enable once it's there."],
    ["“Include” is greyed out on a document.", "Its authenticity hasn't been assessed yet.", "Mark it Verified or Disputed first (Section 5.11)."],
    ["I can only see some of the register.", "Registers show 20 rows per page.", "Use the Previous / Next controls at the foot of the list, or the search box above it (Section 5.5)."],
    ["A Contact RA can't see a case.", "Contact RAs only see cases assigned to them.", "Assign it from the Assigned Contact RA dropdown on the case detail page (Field Coordinator/Admin only)."],
]
story.append(data_table(["Situation", "Likely cause", "What to do"], trouble_rows_internal,
                         [4.6 * cm, 4.6 * cm, PAGE_W - 2 * MARGIN - 9.2 * cm]))

story.append(PageBreak())

# ----------------------------------------------------------- SECTION 10 ---
story.append(h1("10. Quick Reference", key="reference"))
story.append(h2("Addresses"))
story.append(data_table(
    ["What", "Production", "Local development"],
    [["Sign in", "research.agribizframework.com/admin/login", "localhost:3000/admin/login"],
     ["Register organisations/cases", "research.agribizframework.com/admin/organisations", "localhost:3000/admin/organisations"],
     ["Django admin (edge cases only)", "research.agribizframework.com/django-admin/", "localhost:8000/django-admin/"],
     # Escaped: table cells are rendered as Paragraphs, so a bare <token>
     # is parsed as markup and silently disappears from the PDF.
     ["Respondent link shape", "research.agribizframework.com/i/&lt;token&gt;", "localhost:3000/i/&lt;token&gt;"]],
    [3.6 * cm, 7 * cm, PAGE_W - 2 * MARGIN - 10.6 * cm],
))
story.append(Spacer(1, 10))
story.append(h2("Where each role lands after signing in"))
story.append(data_table(
    ["Role", "Lands on"],
    [["PI / Admin, Field Coordinator, Analyst, Supervisor", "/admin/dashboard (Executive Dashboard)"],
     ["Contact RA", "/admin/sample (Main-400 Register)"],
     ["QUAN/Kobo QA RA", "/admin/dashboard/qa (QA Dashboard)"],
     ["KII RA, Documentary RA", "/admin/dashboard/kii-documents (KII/Document Dashboard)"]],
    [8.2 * cm, PAGE_W - 2 * MARGIN - 8.2 * cm],
))
story.append(Spacer(1, 10))
story.append(h2("Further reading (project repository)"))
story.append(Paragraph("&bull; <font face='Courier'>README.md</font> — full technical walkthrough and architecture.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/29_RESPONDENT_GUIDE_AND_MESSAGING.md</font> — message templates in full.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/18_DATA_PRIVACY_AND_COMPLIANCE.md</font> — the full access-control matrix and consent model.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md</font> — the full S00–S16 state machine.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/30_PROIT_MODULE.md</font> — the pre-interview profile tool in full (Section 5.16).", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>backend/api/navigation.py</font> — the single source of truth for which role sees which screens (Section 3.1).", styles["MyBullet"]))

doc.multiBuild(story)
print("wrote", OUT)
