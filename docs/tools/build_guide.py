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
         Paragraph("0773943709 &nbsp;&middot;&nbsp; sales.proagromark2@gmail.com", cover_style_meta)],
        [Paragraph("LIVE AT", ParagraphStyle("m3", parent=cover_style_meta, fontName="Helvetica-Bold", fontSize=8, textColor=GOLD)),
         Paragraph("research.agribizframework.com", cover_style_meta)],
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
story.append(P("1. Open the address above. 2. Enter your username and password. 3. You land on the Executive Dashboard (or, for a role without dashboard access, the first screen your role can open)."))
story.append(h2("2.3 Finding your way around"))
story.append(P(
    "A top navigation bar lists every screen your role can reach. Every screen except the "
    "Executive Dashboard itself also shows a <b>&lt;- Back to &hellip;</b> link at the top "
    "of the page, pointing at its logical parent — a case detail page back to the "
    "register it came from, a sub-dashboard back to the Executive Dashboard, and so on. "
    "<b>Change password</b>, next to “Sign out” (top right), lets you set your own "
    "password at any time — no need to ask the PI/Admin unless you've forgotten it "
    "entirely. Use “Sign out” when you're done, especially on a shared device."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 3 ---
story.append(h1("3. Roles &mdash; Who Can Do What", key="roles"))
story.append(P(
    "Every internal account has exactly one role. Permissions are enforced by the server "
    "on every action, not just hidden buttons — if a screen or button isn't available "
    "to your role, the system will also refuse the underlying request."
))
role_rows = [
    ["PI / Admin", "Everything: every screen and action, the Audit Log, both data exports "
     "(de-identified and full operational), plus Django's own admin site for the handful "
     "of edge cases the Research Operations Centre doesn't cover yet (Section 4)."],
    ["Field Coordinator", "Registering organisations/sample cases (Organisations, "
     "Section 4), sample register &amp; case detail, workflow transitions, "
     "reserve activation, sending/revoking invitations, logging contact attempts, "
     "appointments, cost entries, triggering Kobo sync, the full KII/Documents/QA "
     "workflow, and every aggregate dashboard plus the de-identified export. Everything "
     "except the Audit Log and the operational (contact-identifying) export."],
    ["Contact RA", "Sample register &amp; case detail (read-only), logging contact "
     "attempts, appointment status, and sending/revoking invitations — but only for "
     "cases a Field Coordinator/Admin has <b>assigned</b> to them (Section 5.6). A case "
     "assigned to someone else, or not yet assigned to anyone, simply doesn't appear. No "
     "dashboards, no KII/Documents/QA, no cost logging, no reserve activation or "
     "workflow transitions, no Kobo sync trigger."],
    ["QUAN/Kobo QA RA", "KII register &amp; detail, Documents register &amp; detail, the "
     "QA queue and decisions, and the KII/Document dashboard."],
    ["KII RA", "Same access as QUAN/Kobo QA RA."],
    ["Documentary RA", "Same access as QUAN/Kobo QA RA."],
    ["Analyst", "Every aggregate dashboard and the de-identified export. No write access "
     "anywhere."],
    ["Supervisor (read-only)", "Read-only visibility into everything an internal role can "
     "see — sample register &amp; case detail, contact events &amp; appointments, "
     "KII &amp; Documents &amp; QA queue, invitations, cost entries, and every aggregate "
     "dashboard. Cannot write anywhere, and — unlike Analyst — does not have the "
     "de-identified export."],
]
story.append(data_table(["Role", "Current access"], role_rows, [3.4 * cm, PAGE_W - 2 * MARGIN - 3.4 * cm]))
story.append(Spacer(1, 10))
story.append(note(
    "Assigning a Contact RA to a case",
    "Only a Field Coordinator or Admin can assign (or reassign) which Contact RA owns a "
    "case — from the <b>Assigned Contact RA</b> dropdown on that case's detail page "
    "(Section 5.6). A Contact RA cannot assign cases to themselves or anyone else."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 4 ---
story.append(h1("4. Setting Up Study Data (PI / Admin)", key="setup"))
story.append(P(
    "Registering an organisation and its sample case is done from the Research "
    "Operations Centre itself, at <b>Organisations</b> in the top navigation bar "
    "&mdash; no separate Django admin site needed for this."
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
    ("5", "On the Main case's detail page, use <b>Assigned Contact RA</b> (Section 5.6) "
          "if a specific Research Assistant should handle it. Recording which Reserve "
          "case backs up which Main case (the “Matched case” field) isn't yet exposed as "
          "a button on this page — for a one-off pairing, set it via Django admin "
          "(<font face='Courier'>/django-admin/</font>) under Sample cases."),
]
for num, text in steps_setup:
    story.append(step_row(num, "", text))
story.append(Spacer(1, 6))
story.append(P(
    "Master IDs and Sample IDs are always generated automatically — you never type one "
    "in. A Reserve case starts <b>LOCKED</b> and cannot receive an invitation until it "
    "is deliberately activated (Section 5.11)."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 5 ---
story.append(h1("5. The Research Operations Centre, Screen by Screen", key="screens"))
story.append(P("Every screen below lives under the top navigation bar once signed in."))

story.append(h2("5.1 Executive Dashboard"))
story.append(P("The home screen. Overall progress against the 400 QUAN / 60 KII / 50–75 "
               "document targets, days remaining to the data-lock date, and the "
               "lowest-filled strata (where fieldwork attention is most needed)."))

story.append(h2("5.2–5.4 Sampling / Contact / KII-Document dashboards"))
story.append(P("Reached from the top navigation or a “Back to Executive Dashboard” "
               "link. <b>Sampling</b>: Main-400 counts by province and stratum, reserve "
               "activations by reason. <b>Contact</b>: organisations verified, eligible "
               "respondents identified, invitations sent/opened, appointments upcoming, "
               "refusals, unreachable cases. <b>KII/Document</b>: KII and document counts "
               "against target, broken down by status/type/QA outcome."))

story.append(h2("5.5 Main-400 Register"))
story.append(P("Every Main and Reserve sample case, with its Sample ID, Master ID, "
               "organisation and current status. Click <b>View</b> to open a case's "
               "detail page."))

story.append(h2("5.6 Sample Case Detail"))
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

story.append(h2("5.7 Appointment Queue"))
story.append(P("Every appointment a respondent has requested (phone call, WhatsApp-assisted "
               "session, etc.), with status buttons — Confirmed, Completed, Missed, "
               "Cancelled — restricted to whatever transition is valid from the "
               "current status."))

story.append(h2("5.8 QA Queue"))
story.append(P("Every QUAN submission awaiting a human decision: Accept, Re-query, or "
               "Reject, each requiring a note. At the top, the <b>KoboToolbox sync</b> "
               "panel shows when data last pulled from Kobo and lets you trigger a pull "
               "on demand (“Sync now”) instead of waiting for the next scheduled "
               "run."))

story.append(h2("5.9 KII Register"))
story.append(P("The list of Key Informant Interview records, a button to create a new one, "
               "and a detail page per record for: advancing its status (Invited -&gt; "
               "Scheduled -&gt; Completed/Declined/No-show), recording participation and "
               "recording consent as two <i>separate</i> decisions, and tracking transcript "
               "and coding progress. A KII cannot be marked Completed with a recording "
               "unless recording consent was captured first — this is enforced by the "
               "system, not just a reminder."))

story.append(h2("5.10 Documents"))
story.append(P("The documentary-evidence corpus, a button to add a new record, and a "
               "detail page per document for: assessing authenticity (Verified/Disputed) "
               "and setting QA status (Included/Excluded). A document cannot be marked "
               "Included until its authenticity has been assessed — also enforced by "
               "the system."))

story.append(h2("5.11 Reserve Activation"))
story.append(P("Every currently-LOCKED Reserve case. Activating one always requires picking "
               "one of five authorised reasons (Ineligible, Inactive, Duplicate, Refusal, "
               "Nonresponse exhausted) and writing an evidence note — there is "
               "deliberately no free-text “other” option. Once activated, the "
               "case can receive its own invitation."))

story.append(h2("5.12 Cost Dashboard"))
story.append(P("Total fieldwork spend, cost per QA-passed QUAN submission, cost per "
               "completed KII, a breakdown by category, and a form to log a new cost "
               "event (date, category, amount)."))

story.append(h2("5.13 Audit Log"))
story.append(P("Every sensitive action ever taken in the system — consent recorded, "
               "invitation issued/revoked, reserve activated, workflow transition "
               "(including rejected attempts), KII/document status changes, QA decisions "
               "— each correctly attributed to the signed-in user who performed it. "
               "PI/Admin only."))

story.append(h2("5.14 Data Export"))
story.append(P("Two CSV downloads, deliberately different in shape. The "
               "<b>de-identified analysis export</b> has no name, phone, email or "
               "gatekeeper field — safe to share with the wider research team. The "
               "<b>full operational export</b> includes contact details and is "
               "PI/Admin-only, for internal fieldwork use, never distributed externally."))

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
    ("4", "Reads the study information", "Purpose, confidentiality, and their rights, in a short mobile-readable page.", None),
    ("5", "Gives consent", "An explicit “I agree to take part” action — never a pre-ticked box. They may decline at any point.", "GATE"),
    ("6", "Chooses how to answer", "Themselves right now, or a phone-assisted / WhatsApp-assisted / scheduled session instead.", None),
    ("7", "Answers the questionnaire", "Opens the KoboToolbox form directly.", None),
    ("8", "Done", "A neutral thank-you screen. No score, rating, or financing decision is ever calculated or shown.", None),
]
for num, title, body, tag in resp_steps:
    story.append(step_row(num, title, body, tag))
story.append(Spacer(1, 10))
story.append(note(
    "If a respondent doesn't fit any role on the list",
    "This is the intended outcome for someone who isn't a knowledgeable organisational "
    "respondent — no answers are recorded from them, and <i>Respondent.is_eligible</i> "
    "stays false. Ask them to nominate the correct person at that organisation, then issue "
    "that person their own, separate invitation."
))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 8 ---
story.append(h1("8. A Complete Walkthrough", key="walkthrough"))
story.append(P("Start to finish, for one new organisation."))
walk_steps = [
    ("1", "PI/Admin registers the Main organisation and its matched Reserve in Django admin (Section 4)."),
    ("2", "Field Coordinator opens the Main case's detail page and advances its workflow status through verification (S01 -&gt; S02 -&gt; S03) as the organisation and an eligible respondent are confirmed."),
    ("3", "Field Coordinator sends the invitation from the case detail page, copies the link, and sends it using one of the message templates."),
    ("4", "The case's workflow status advances automatically to Invitation sent (S05) the moment the invitation is issued."),
    ("5", "The respondent opens the link, confirms eligibility, consents, and either completes the questionnaire themselves or requests assisted completion — logged as an Appointment if so."),
    ("6", "On submission, the scheduled Kobo reconciliation job (or a manual “Sync now”) pulls the response into the QA queue."),
    ("7", "A QUAN/Kobo QA RA reviews the submission and records Accept, Re-query, or Reject."),
    ("8", "Once QA-passed, the submission counts toward the Executive Dashboard's progress figures."),
    ("9", "At data lock, PI/Admin runs the de-identified analysis export for the wider research team, and the full operational export for internal records."),
]
for num, text in walk_steps:
    story.append(step_row(num, "", text))

story.append(PageBreak())

# ------------------------------------------------------------ SECTION 9 ---
story.append(h1("9. Troubleshooting", key="troubleshooting"))
trouble_rows = [
    ["“The link says it's not valid.”", "Typo, or the link expired / was superseded by a newer one.", "Open the case's detail page and send a new invitation — it issues a fresh link and invalidates the old one."],
    ["“I already did this.”", "Already completed, or a new wave was issued since.", "Check the Invitations history on the case detail page for the current status before re-issuing."],
    ["“I'm not the right person to answer this.”", "Doesn't fit any listed role category.", "The intended ineligible path — no answers are recorded. Ask them to nominate the right person."],
    ["“Will my financing be affected by my answers?”", "Reasonable concern given the study's subject.", "No — no score, rating, or financing decision is ever generated or shown, at any point."],
    ["A screen shows “Forbidden” or won't load an action.", "Your role doesn't have permission for that screen/action.", "Check Section 3's role table — permissions are enforced server-side, not just hidden buttons."],
]
story.append(data_table(["Situation", "Likely cause", "What to do"], trouble_rows,
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
     ["Respondent link shape", "research.agribizframework.com/i/<token>", "localhost:3000/i/<token>"]],
    [3.6 * cm, 7 * cm, PAGE_W - 2 * MARGIN - 10.6 * cm],
))
story.append(Spacer(1, 10))
story.append(h2("Further reading (project repository)"))
story.append(Paragraph("&bull; <font face='Courier'>README.md</font> — full technical walkthrough and architecture.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/29_RESPONDENT_GUIDE_AND_MESSAGING.md</font> — message templates in full.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/18_DATA_PRIVACY_AND_COMPLIANCE.md</font> — the full access-control matrix and consent model.", styles["MyBullet"]))
story.append(Paragraph("&bull; <font face='Courier'>docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md</font> — the full S00–S16 state machine.", styles["MyBullet"]))

doc.multiBuild(story)
print("wrote", OUT)
