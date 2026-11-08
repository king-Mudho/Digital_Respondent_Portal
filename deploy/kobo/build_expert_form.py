"""Builds the KoboToolbox XLSForm for the ABI expert content-validation questionnaire, Round 1, from
backend/apps/experts/instrument.py (the same definition the portal uses). Run: python deploy/kobo/build_expert_form.py

The Expert ID is filled in by the portal's personal link and cannot be typed over, so every submission matches its
expert; the form refuses to go further if any of the three consent statements is answered No. Ratings are optional
(the information sheet says any question may be skipped); U = unable to judge asks for a short reason.
"""
import importlib.util
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("instrument", ROOT / "backend/apps/experts/instrument.py")
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)

# AGENTS.md rule 2: none of these may appear anywhere an expert can read it.
FORBIDDEN = ["approved", "loan approval", "credit rating", "bankability score", "guarantee"]
found = [p for p in FORBIDDEN if re.search(r"(?<![\w])" + re.escape(p), I.all_text(), re.IGNORECASE)]
assert not found, f"Forbidden wording in the instrument: {found}"

OUT = Path(__file__).with_name("ABF-FST_ABI_Expert_Validation_Round1_v1.0_KOBO.xlsx")
COLS = ["type", "name", "label", "hint", "required", "relevant", "appearance", "read_only", "constraint",
        "constraint_message", "default"]
rows = []


def row(type_, name="", label="", **kw):
    rows.append({"type": type_, "name": name, "label": label, **kw})


for meta in ("start", "end", "today"):
    row(meta, meta)

# Section A, the Expert ID, and Section B
row("begin_group", I.GROUP, "A. Information for invited experts", appearance="field-list")
row("note", "info_intro", "**" + I.FORM_TITLE + "**\n\nABF–FST Publication 2 • Zimbabwe • Instrument version 1.0\n"
    "Researcher: Happyson Saina | PhD Candidate, Chinhoyi University of Technology")
for n, (title, text) in enumerate(I.INFORMATION, 1):
    row("note", f"info_{n}", f"**{title}.** {text}")
row("note", "info_ethics", I.ETHICS_LINE)
row("text", I.EXPERT_ID_FIELD, "Expert ID", hint="Filled in from your personal invitation link.", required="yes",
    read_only="yes", constraint="regex(., '^E[0-9]{2,3}$')", constraint_message="Open this form from your personal invitation link.")
row("end_group")

row("begin_group", "part_b", "B. Consent and professional profile", appearance="field-list")
for name, text in I.CONSENT_STATEMENTS:
    row("select_one yes_no", name, text, required="yes")
CONSENTED = " and ".join(f"${{{name}}} = 'yes'" for name, _ in I.CONSENT_STATEMENTS)
NOT_CONSENTED = " or ".join(f"${{{name}}} = 'no'" for name, _ in I.CONSENT_STATEMENTS)
row("note", "consent_stop", "Thank you. Without all three statements the questionnaire cannot continue, and nothing "
    "more is asked. You may close this form.", relevant=NOT_CONSENTED)
row("select_one yes_no", "ROUND2_CONTACT", "I agree to be contacted for an optional second rating round.",
    relevant=CONSENTED)
row("date", "RESPONSE_DATE", "Date", relevant=CONSENTED, default="today()")
row("select_one experience", "EXPERIENCE", "Years of relevant experience", relevant=CONSENTED)
row("text", "EXPERIENCE_OTHER", "Other: please specify", relevant="${EXPERIENCE} = 'other'")
row("select_one expertise", "EXPERTISE", "Primary expertise (choose one)", relevant=CONSENTED)
row("text", "EXPERTISE_OTHER", "Other: please specify", relevant="${EXPERTISE} = 'other'")
row("select_one institution", "INSTITUTION", "Institution category", relevant=CONSENTED)
row("text", "INSTITUTION_OTHER", "Other: please specify", relevant="${INSTITUTION} = 'other'")
row("text", "CONFLICTS", "Potential conflicts of interest affecting assessment (optional description)",
    relevant=CONSENTED, appearance="multiline")
row("end_group")

# Section C and D
row("begin_group", "part_c", "C. Rating instructions", appearance="field-list", relevant=CONSENTED)
row("note", "instructions", I.RATING_INSTRUCTIONS)
for key, (letter, title, labels) in I.SCALES.items():
    row("note", f"scale_{key}", f"**{title.upper()} ({letter}):** " + " | ".join(f"{n} {lab}" for n, lab in enumerate(labels, 1)))
row("end_group")

row("begin_group", "part_d", "D. Sixteen-indicator assessment", relevant=CONSENTED)
for code, title, definition, items in I.DOMAINS:
    row("begin_group", code, f"{code}. {title}")
    row("note", f"{code}_definition", f"*Domain definition:* {definition}")
    for ind, ind_title, ind_text in items:
        row("begin_group", ind, f"{ind} — {ind_title}", appearance="field-list")
        row("note", f"{ind}_text", ind_text)
        for key, (letter, scale_title, _) in I.SCALES.items():
            row(f"select_one {key}", f"{ind}_{letter}", f"{scale_title} ({letter})", appearance="horizontal-compact")
        any_u = " or ".join(f"${{{ind}_{letter}}} = 'U'" for letter, _, _ in I.SCALES.values())
        row("text", f"{ind}_U_REASON", "You chose U (unable to judge): please explain briefly", relevant=any_u)
        row("text", f"{ind}_COMMENT", "Comment / suggested revision (optional)", appearance="multiline")
        row("end_group")
    row("text", f"{code}_COMMENT", f"Domain-level comment on {code} (missing concepts, overlap, applicability)",
        appearance="multiline")
    row("end_group")
row("end_group")

# Section E
row("begin_group", "part_e", "E. Overall ABI assessment", appearance="field-list", relevant=CONSENTED)
for n, (name, question, kind, follow, follow_label, when) in enumerate(I.OVERALL, 1):
    label = f"{n}. {question}"
    if kind == "text":
        row("text", name, label, appearance="multiline")
    else:
        row(f"select_one {kind}", name, label)
    if follow:
        row("text", follow, follow_label, appearance="multiline",
            relevant=f"${{{name}}} = '{when}'" if when else f"${{{name}}} != ''")
row("end_group")
row("note", "thanks", "Thank you. Please submit the form.", relevant=CONSENTED)

choices = [("yes_no", "yes", "Yes"), ("yes_no", "no", "No"),
           ("yes_no_unsure", "yes", "Yes"), ("yes_no_unsure", "no", "No"), ("yes_no_unsure", "unsure", "Unsure")]
for list_name, options in (("experience", I.EXPERIENCE), ("expertise", I.EXPERTISE), ("institution", I.INSTITUTION)):
    choices += [(list_name, name, label) for name, label in options]
for key, (_, _, labels) in I.SCALES.items():
    choices += [(key, str(n), f"{n} {label}") for n, label in enumerate(labels, 1)]
    choices.append((key, I.UNABLE[0], I.UNABLE[1]))

wb = openpyxl.Workbook()
survey = wb.active
survey.title = "survey"
survey.append(COLS)
for r in rows:
    survey.append([r.get(c, "") for c in COLS])
ch = wb.create_sheet("choices")
ch.append(["list_name", "name", "label"])
for c in choices:
    ch.append(list(c))
st = wb.create_sheet("settings")
st.append(["form_title", "form_id", "version", "style"])
st.append([I.FORM_TITLE, I.FORM_ID, I.FORM_VERSION, "pages"])
readme = wb.create_sheet("README")
for line in [
    "ABF-FST — ABI expert content-validation questionnaire, Round 1 (instrument version 1.0, 6 November 2026)",
    "",
    "Before deploying: replace the three [INSERT ...] values in part_a / info_ethics (ethics approval number, research",
    "email, supervisor contact) — the questionnaire says it is distributed only after the required approval.",
    "",
    "Deploy as a NEW KoboToolbox project, then give the portal its asset UID and web-form link:",
    "   KOBO_EXPERT_ASSET_UID and KOBO_EXPERT_FORM_URL on the server (deploy/configure-kobo.sh).",
    "Experts open it only from their personal portal link, which fills in part_a/EXPERT_ID (E01, E02, ...) after",
    "they have given consent on the portal. The Expert ID cannot be typed over, so each submission matches its expert.",
    "",
    "Section F (researcher-only I-CVI analysis and decision rules) is deliberately not in the form.",
]:
    readme.append([line])
for ws in (survey, ch, st):
    for c in ws[1]:
        c.font = Font(bold=True)
survey.column_dimensions["B"].width = 22
survey.column_dimensions["C"].width = 80
wb.save(OUT)
print("wrote", OUT, "|", len(rows), "survey rows,", len(choices), "choices")
