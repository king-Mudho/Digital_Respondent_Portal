# 31 — QA thresholds and Participant Information Sheet: review and sign-off pack

**Status: awaiting sign-off.** Prepared 2026-09-13 for the Principal Researcher,
supervisors (Dr L. Chikazhe, Dr J. Kanyepe) and the CUT Research Ethics office.

Two items have been running on engineering defaults since Phase 0 and are recorded as
open in `27_AGENT_EXECUTION_PLAN.md`. Both are research decisions, not engineering ones,
and neither has been reviewed by anyone qualified to approve it. This document exists
because they were previously only readable inside a database migration and a TypeScript
constant — there was nothing a reviewer could actually read and sign.

Nothing here is a recommendation to keep the current values. They were chosen to make the
system concretely testable, not because they are methodologically justified.

---

# Part A — QUAN QA rule thresholds

Source of truth: `QARuleThreshold` rows in the database, seeded from
`backend/apps/qa/services.py::DEFAULT_THRESHOLDS`. They are data, not hardcoded literals,
so a value can be changed without a redeploy and every change is attributable
(`set_by`, `effective_from`).

## A1. What is actually enforced today

Of the nine configured thresholds, **three are active**, five are dormant pending the
real KoboToolbox form, and one is never read at all. That distinction matters for
sign-off: approving a value that nothing evaluates gives false assurance.

| Threshold | Value | State |
|---|---|---|
| `min_plausible_duration_seconds` | 300 (5 min) | **Active since 2026-09-14** — see note below |
| `max_plausible_duration_seconds` | 5400 (90 min) | **Active since 2026-09-14** — see note below |
| `duplicate_master_id_window_hours` | 24 | **Active** |
| `required_field_names` | 65 fields from the deployed form | **Active since 2026-09-14** — set by `qa_required_fields_from_kobo`: the resolved Sample_ID, ADMIN_DATE, E1, P1–P10, all 58 Likert items and D1–D2 (every question the form requires and shows to every consenting respondent). A declined or ineligible respondent's submission is therefore flagged, which is intended |
| `optional_field_names` | `[]` | Dormant — empty |
| `max_missing_optional_fields_percent` | 10 | Dormant — guarded by `optional_field_names` being non-empty |
| `logic_violation_hard_stop_rules` | `[]` | Dormant — no rules defined |
| `logic_violation_soft_flag_rules` | `[]` | Dormant — no rules defined |
| `mode_imbalance_alert_ratio` | 0.70 | **Not implemented** — defined but never read by `evaluate_submission()` |

**Correction, 2026-09-14.** The two duration thresholds were listed as active, but
reconciliation never recorded `completion_seconds`, so they could not fire on any real
submission. They can now: a submission's duration is the form's own `end` − `start`.

**Two more texts need approval alongside the PIS:** the WhatsApp invitation message
(`invitationMessage` in the case page) and the two reminder texts seeded as
`drp_reminder_day2` / `drp_reminder_day7_final` (editable in Django admin). They are what
RAs now send by hand from the Follow-ups screen.

The four remaining dormant thresholds cannot be populated until the real Kobo form's field names
are frozen (`11_KOBOTOOLBOX_INTEGRATION.md`, and the open Kobo item in `docs/27`). They
are listed here so the reviewer knows the QA engine is currently thinner than
`15_QA_AND_DATA_QUALITY.md` describes.

No submission ever reaches `QA_PASSED` automatically. Every one of these rules produces a
*flag* for human review; only a human `QAEvent` with a mandatory note can pass a
submission. A wrong threshold therefore creates review workload or misses a prompt — it
does not by itself admit bad data.

## A2. The three active thresholds — decisions required

### A2.1 `min_plausible_duration_seconds` — currently **300 seconds (5 minutes)**

Flags a submission completed faster than this as implausibly quick.

- **Too low** — straight-lining and careless completion pass unflagged.
- **Too high** — genuinely fast, competent respondents are flagged, creating review work
  and potentially implying bad faith where there is none.
- **To judge it:** how quickly could a well-prepared finance director who knows their
  figures complete the instrument? The questionnaire is described to respondents as
  taking 15–25 minutes.

**Decision:** keep 300 / change to ______ seconds. Rationale: ____________________

### A2.2 `max_plausible_duration_seconds` — currently **5400 seconds (90 minutes)**

Flags a submission that took longer than this.

- **Too low** — flags every respondent who was interrupted, which in a fieldwork context
  is common and not a quality signal at all.
- **Too high** — a form left open for hours, then completed from memory, is not caught.
- **To judge it:** does Kobo measure elapsed wall-clock time from first open to submit
  (in which case interruptions dominate and this should be generous), or active time?
  **This is currently an assumption and should be confirmed against the real Kobo asset
  before the value is fixed.**

**Decision:** keep 5400 / change to ______ seconds. Rationale: ____________________

### A2.3 `duplicate_master_id_window_hours` — currently **24 hours**

Flags a second submission from the *same organisation* within this window.

- **Too short** — a genuine duplicate submitted the next day is not flagged.
- **Too long** — legitimate re-submissions after an RA-assisted correction are flagged.
- **Note:** the rule keys on the organisation (`Master_ID`), not the respondent, so two
  different people at the same organisation submitting within the window will flag. Given
  the design samples one respondent per organisation, that is probably the intent — but
  it is worth confirming rather than assuming.

**Decision:** keep 24 / change to ______ hours. Rationale: ____________________

## A3. Items for the reviewer to note, not approve

- `mode_imbalance_alert_ratio` (0.70) is configured but never evaluated. Either it should
  be implemented or removed; leaving it in place implies a control that does not exist.
- The five dormant thresholds should be revisited once the Kobo asset exists, and this
  document re-issued for that part.

---

# Part B — Participant Information Sheet

Current version **v1.3**, live at `/i/<token>/information` and shown before consent. v1.3 (2026-09-14) changes only the study contact email, to abffst.research.cut@gmail.com.
Source: `frontend/lib/constants/participantInformation.ts`. The version string is recorded
against every `ConsentRecord`, so consent is always traceable to the exact wording the
respondent saw. **Bump the version whenever the text changes.**

> **v1.2 (2026-09-13, PI-directed) adds the PROIT disclosure** — gap B2.1 below, which was
> the most material of the seven. That closes the gap in the *text*. It does not make the
> wording approved: the PIS as a whole has still never been reviewed by the ethics office,
> and the remaining six gaps are untouched. The sign-off block at the end of this document
> is still open.

## B1. The text as it currently stands

> This study is being carried out by Happyson Saina, a doctoral researcher at Chinhoyi University of Technology, supervised by Dr L. Chikazhe and Dr J. Kanyepe. It looks at how agribusinesses in Zimbabwe can become better prepared for financing and investment. This study has received ethics clearance from Chinhoyi University of Technology (Research Ethics Clearance Letter, Annex 19, Form GRSD 17 SEBS/06/2025).
>
> Your organisation has been selected to take part. If you agree, you will be asked to complete a questionnaire about your organisation (around 15-25 minutes), either yourself online, or with help from a researcher by phone or WhatsApp if you prefer.
>
> Before contacting you, we may look up information about your organisation that is already publicly available — for example from official registers, published reports, or reputable news sources — so that we do not ask you for facts that are already on record. Where we have done this, you will be shown what we found and asked to confirm or correct it. You can also tell us you do not know, that you would rather not say, or skip this step altogether. It is there to save you time, not to test you. What you tell us is always recorded separately from what we found, and your own answers take precedence over it.
>
> Taking part is voluntary. You can decline, or stop at any time, without any consequence. Your answers are used for research purposes only — no score, rating, or financing decision is generated or shown to you, and your individual answers will never be shared with any lender or financial institution.
>
> Your name and contact details are kept separately from your answers and are only used to manage your participation in this study (for example, to send a reminder or arrange a call). Only the research team can see this information. Results will only ever be reported in combined, anonymised form.
>
> If you have any questions, you can contact the research team: Happyson Saina, phone 0773943709, email abffst.research.cut@gmail.com. The same details are also included in your invitation message.

## B2. Gaps a reviewer will likely want addressed

These are raised for the ethics office to rule on. They are omissions from the text, not
defects in the system.

1. ~~**PROIT background research is not disclosed.**~~ **ADDRESSED in v1.2
   (2026-09-13).** Before contact, the research team may compile a profile of the
   respondent's organisation from public sources — statutory registers, official reports,
   media — which the respondent is then asked to confirm or correct
   (`30_PROIT_MODULE.md`, live and respondent-facing). The verification screen explained
   this at the point of use, but the information sheet the respondent consents on the
   basis of did not mention it at all. v1.2 adds a paragraph covering what is looked up,
   from what kinds of source, what the respondent will be asked to do with it, that they
   may decline or skip, and that their own answers are recorded separately and take
   precedence. **Still for the reviewer to confirm:** whether that wording is sufficient
   disclosure, and whether it sits in the right place in the sheet.
2. **No retention or destruction statement.** How long identifying contact data is kept,
   and what happens to it after the 30 November 2026 data lock. `18_DATA_PRIVACY_AND_
   COMPLIANCE.md` has a position; the PIS does not state it.
3. **No withdrawal-after-submission route.** The text covers stopping *during*
   participation ("stop at any time"). It does not say whether a respondent can withdraw
   their data afterwards, or how. A procedure exists (`10_INVITATION_AND_CONSENT.md`).
4. **No independent complaints route.** Questions go to the researcher. Ethics guidance
   commonly expects a named contact independent of the research team — typically the
   ethics committee or a supervisor — for concerns the respondent does not want to raise
   with the researcher directly.
5. **"Only the research team can see this information"** — worth confirming this is
   accurate and sufficient given the eight internal roles and the read-only Supervisor
   and external-examiner access that may follow.
6. **Data storage location is not stated.** Data is held on a VPS; whether the PIS needs
   to say where, and under whose jurisdiction, is an ethics-office call.
7. **Language.** The interface is English-only for v1.0
   (`19_LANGUAGE_AND_ACCESSIBILITY.md` flags Shona/Ndebele translation as an open,
   low-cost mitigation). Whether an English-only PIS is acceptable for this respondent
   population is a decision for the ethics office.

**Decision:** approve v1.3 as-is / approve with the amendments attached / revise and
re-issue as v1.3. Rationale: ____________________

---

# Sign-off

No value or wording above should be treated as approved until this block is completed.
Once it is, record the outcome in `27_AGENT_EXECUTION_PLAN.md`'s open questions, update
the relevant `QARuleThreshold` rows (with `set_by` set to the approving user, not left
null), and bump `PARTICIPANT_INFORMATION_SHEET_VERSION` if the wording changed.

| | Name | Role | Decision | Date | Signature |
|---|---|---|---|---|---|
| Part A — QA thresholds | Happyson Saina | Principal Researcher | Approved as configured | 2026-09-15 | Written instruction in the build session; audit `qa.thresholds_approved` |
| Part A — invitation and reminder wording | Happyson Saina | Principal Researcher | Approved as live | 2026-09-15 | Audit `messaging.wording_approved` |
| Part A — invitation wording, amendment | Happyson Saina | Principal Researcher | Approved: add the closing line "Questions: Happyson Saina, 0773943709, abffst.research.cut@gmail.com" so the invitation carries the contact details the PIS refers to | 2026-09-16 | Written instruction in the build session |
| Part A — QA thresholds | | Supervisor | | | |
| Part B — PIS wording (v1.3) | Happyson Saina | Principal Researcher | Approved; stated to be covered by his CUT student research clearance (ethics and POTRAZ) | 2026-09-15 | Written statement in the build session |
| Part B — PIS wording | | Supervisor | | | |
| Part B — PIS wording | | CUT Research Ethics | Covered by the study's existing clearance, per the PI | | |

Until Part B is signed, the PIS remains a draft that respondents are nonetheless being
shown. Until Part A is signed, the QA thresholds remain engineering defaults. Both are
listed as go-live blockers in `28_DEFINITION_OF_DONE.md`.
