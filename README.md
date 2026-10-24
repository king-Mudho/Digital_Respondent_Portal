# ABF-FST Digital Respondent Portal

A research-operations platform supporting *"Developing and Validating the Agribusiness
Bankability Framework for Food Systems Transformation through Novel Financing Models in
Zimbabwe"* (ABF-FST). Principal Researcher: Happyson Saina, Doctor of Strategic
Management candidate, Chinhoyi University of Technology (Supervisors: Dr L. Chikazhe,
Dr J. Kanyepe).

The portal authenticates and routes the study's selected Main-400 respondents (plus a
locked Reserve-400), captures consent and eligibility, launches the KoboToolbox
questionnaire with controlled identifiers, reconciles submissions, and runs the KII,
documentary-evidence, contact/CRM, QA and fieldwork-cost operations behind the 400 QUAN
/ 60 KII / 50–75 document data-collection target. It is **not** a public survey tool and
does **not** expose any ABI bankability score to respondents — see
`docs/00_PROJECT_MASTER.md` for full project identity and `docs/20_EMBEDDING_WITH_ABI.md`
for why it is deliberately kept separate from the public ABI self-assessment demo.

## Status

**Built, deployed and engineering-ready for go-live** at
**[research.agribizframework.com](https://research.agribizframework.com)**
(`docs/33_GO_LIVE_READINESS.md`). Issuing the first real Main-400 invitation remains the
PI's decision.

**Where fieldwork stands (15 Sep 2026)**

- **Registers loaded:** 400 Main and 400 Reserve sample cases across 800 organisations
  with all 400 pairs wired, 90 KII records (Core-60 plus Reserve-30), 100
  documentary-evidence records.
- **Connected to KoboToolbox:** the Main Study Questionnaire, KII Guide and Document
  Analysis Tool. Scheduled sync and the webhook both run against the live forms.
  Required-field QA uses 65 fields read from the live questionnaire.
- **Approvals recorded by the PI (15 Sep 2026):** the ethics and POTRAZ position (covered
  by his CUT student research clearance), PROIT, Participant Information Sheet v1.3 (now v1.5), the
  QA thresholds, and the invitation and reminder wording. Each is audited
  (`qa.thresholds_approved`, `messaging.wording_approved`) and recorded in `docs/28`,
  `30`, `31` and `33`.
- **Cases ready for contact:** all 400 Main cases are assigned to a Contact RA and moved
  through verification to **S03 Eligible respondent identified**. Every transition is
  audited.
- **Checks:** `manage.py golive_preflight` passes **15/15** on production. Its writes
  are rolled back and row counts are confirmed unchanged.

**Still with the team before the first invitation:**

- Create named staff accounts from `docs/templates/ABF-FST_Staff_Accounts_Template.xlsx`.
- Collect respondent contact details (347 Main cases have none).
- Rotate the KoboToolbox password and API token.
- Add the Gmail App Password (`deploy/configure-email.sh`).
- Do the one-time Google Drive sign-in for offsite backups.
- Run a user-acceptance invitation on a real phone.

SMS and WhatsApp through Twilio are optional (`deploy/configure-twilio.sh`): until they
are set up, invitations go out by hand from the shared study WhatsApp number and the Day 2 /
Day 7 reminders wait on Follow-ups. AI-assisted document coding
(`deploy/configure-ai-coding.sh`) is also optional and needs the PI's own Anthropic API
key (a paid, per-request cost) — the Documentary RA workflow works fully by hand without it.

**Quality passes.** Seven passes have run against this codebase, by hand in a real
browser as well as by test:

1. **Hardening pass:** every screen and endpoint.
2. **Role, register and respondent-flow audit.**
3. **Go-live audit (14 Sep):** private payload storage, signed questionnaire links,
   reminders that actually reach people, withdrawal, contact details, Kobo edit and
   time-zone handling.
4. **Every-screen, every-role audit (15 Sep):** at desktop and phone widths, plus a
   performance pass.
5. **Document analysis on the platform (16 Sep):** a prefilled coding link and source-file
   upload/download for the Documentary Evidence module.
6. **The KII Guide's own prefilled link (17 Sep):** the same idea, narrower and
   consent-gated because it identifies a person rather than a document.
7. **AI-assisted document coding, human-reviewed (17 Sep):** a full draft coding of the
   Document Analysis Tool from the uploaded source file, reviewed and submitted by a
   Documentary RA — never generated and filed automatically.

All are itemised under [Notable fixes](#notable-fixes).

**Current state:**

- Backend: **458 tests** passing (`pytest`).
- Playwright: **48 E2E tests** pass in CI. **3 are skipped** on purpose: WhatsApp, and the two
  Kobo download tests when no KoboToolbox is reachable.
- `ruff check`, `tsc --noEmit` and `eslint` are all clean.

The full documentation set for users is under [Documentation](#documentation): a system
manual, one guide per role, and a respondent guide.

This is a research-operations tool supporting an active fieldwork study with a
30 November 2026 data-lock date — not a production lending or credit-decision system.
See `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` for the compliance position.

---

## How the portal works, step by step

The portal has two halves that share one Django backend: a **public, invitation-gated
respondent flow** (nobody can browse in — every visit starts from a personal link) and
an **internal Research Operations Centre** for the PI, admins, field coordinators and
analysts.

### 1. Sampling and identifiers (the foundation)

The Main-400/Reserve-400 registers were loaded by `manage.py import_quan_register` from
the approved sampling register. Organisations added afterwards are registered from
`/admin/organisations` in the Research Operations Centre, which also creates the sample
case and (from the case detail page) pairs it with its matched Reserve — Django admin is
not needed for any part of this.

**Organisations** are stratified by **province × actor family × size class**. Entity type
and value chain are recorded as free-text descriptive fields and are deliberately *not*
part of the stratum match — the schema originally assumed value chain was a stratum
dimension, which the real register contradicted. Each slot in the design has one **Main**
case and one locked **Reserve** case. Every organisation gets a system-generated
`Master_ID` (`MID-<province>-<sequence>`) and every sample case a `Sample_ID`
(`SID-<year>-<sequence>`), both assigned via a DB-sequence with row locking so two
concurrent requests can never collide — never user-entered, never reused.

A Main case's `Sample_ID` moves through a fixed **S00–S16 workflow status**, validated
by `apps.sampling.services.transition_workflow_status()` — nothing else in the codebase
is allowed to change it:

| Status | Meaning |
|---|---|
| S00 | Selected Main |
| S01 | Verification required |
| S02 | Organisation verified |
| S03 | Eligible respondent identified |
| S04 | Invitation prepared |
| S05 | Invitation sent |
| S06 | Invitation opened |
| S07 | Survey started |
| S08 | Survey submitted |
| S09 | QA query |
| S10 | QA passed |
| S11 | Completed |
| S12 | Refused |
| S13 | Nonresponse |
| S14 | Ineligible |
| S15 | Duplicate/inactive |
| S16 | Reserve eligible for activation |

S12–S15 are terminal "drop" states — a case that lands in one of them makes its matched
Reserve case eligible for **activation** (S16), which always requires one of five
documented reasons (ineligible, inactive, duplicate, refusal, nonresponse exhausted) plus
a human-written evidence note, and is written atomically with an audit-log entry. A
Reserve case can never be invited while `LOCKED` — this is enforced in the database
service layer, not just hidden in the UI.

### 2. The respondent-facing flow (`/i/<token>`, screens R01–R10)

An admin issues a personal invitation (32-byte random token, only its salted SHA-256
hash ever stored; a matching 8-character manual code exists for phone-assisted
administration). The respondent's link looks like
`https://research.agribizframework.com/i/<token>` and walks through:

1. **R02 Invitation validation** — the token is checked (not expired, not revoked, not
   superseded by a newer one issued to the same case).
2. **R03 Organisation confirmation** — respondent confirms they represent the named
   organisation.
3. **R04 Eligibility gate** — respondent selects their role from a fixed list (owner,
   CEO/MD, finance/credit/risk, operations, strategy/BD, supply chain/commercial, other
   senior manager). Anyone outside this list is routed to a referral message, never
   silently marked eligible.
4. **R05 Participant information** — the study information sheet, followed by the
   Research Clearance section if the PI has published one or more official approval
   letters. See [Research Clearance](#research-clearance--verifying-the-study-is-genuine).
5. **R06 Electronic consent** — participation consent, captured as its own
   `ConsentRecord` row.
6. **PROIT verification** (`/i/<token>/verify`) — if a locked pre-profile exists for the
   case, the respondent confirms, corrects, or declines each background fact the research
   team already gathered, instead of answering it from scratch. Self-skips entirely when
   there is nothing to verify, and can be skipped by the respondent regardless: it is a
   burden reduction, not an extra gate. See [PROIT](#proit--pre-interview-profiling).
7. **R07 Participation choice** — complete it now (web self-administration), have a
   researcher call, or a WhatsApp-assisted session.
8. **R08 Kobo questionnaire redirect** — requires **both** a passed eligibility check and
   `GIVEN` participation consent, enforced server-side in
   `apps.kobo.services.build_redirect_url()` — the single point every caller goes through,
   not a disabled button. Opens the public KoboToolbox web form (`KOBO_FORM_URL`) with
   `Master_ID`, `Sample_ID`, administration mode, role category and a **signed** token
   reference (`<id>.<hmac>`) as hidden fields. The respondent needs no Kobo account. The
   case moves to S07 Survey started.
9. **R09 Appointment request** — if the respondent asked for a call instead, this
   captures a preferred time/mode. Also consent-gated (PI decision, Sep 2026): an
   appointment records a named person's availability against an identified organisation
   and places them on an RA's call list, so it sits behind the same gate as the
   self-administered route. Times must be in the future, enforced at both layers.
10. **R10 Completion** — a neutral closing page. Someone who completed the questionnaire
    is thanked for participating; someone who booked a call is told a researcher will be
    in touch, since they have *not* finished. No score, rating, or financing decision is
    ever shown here or anywhere else in this flow.

Every step reports failure in plain language and leaves the respondent able to retry.
Before the Sep 2026 audit each step wrapped its submit in `try/finally` with no `catch`,
so an expired token, a throttled request or a dropped connection left the button
re-enabled and the page unchanged — indistinguishable from a dead button, to someone
with no support channel open.

### 3. KoboToolbox integration (the actual questionnaire)

KoboToolbox is the sole authority for the QUAN questionnaire's logic and capture — this
app never re-implements branching or validation. The catch: **Kobo's webhook only fires
on new-submission creation, never on a later edit**. Relying on it alone would silently
lose every RA correction or respondent edit made after first submission. So:

- The webhook (`POST /api/v1/kobo/webhook/`, shared-secret protected) is only ever a
  fast "heads-up" that triggers an early reconciliation run — it never writes
  `QUANSubmission` rows itself.
- A **Celery Beat scheduled job** (every 15 minutes during active fieldwork hours, 60
  overnight — both configurable) is the actual source of truth: it pulls the full
  submission list from Kobo's `/api/v2/assets/{asset_uid}/data/` endpoint (following
  pagination — see [Notable fixes](#notable-fixes)), computes a
  content hash of each payload, and treats any change in that hash as an edit, re-queuing
  the submission for QA review rather than silently keeping a stale QA status.
- A submission whose `sample_id` doesn't match any known `SampleCase` is flagged as a
  mismatch and audited — never dropped, never auto-matched to the nearest case.
- **Identity, time and duration are taken from Kobo's own fields.** A submission is keyed
  on `meta/rootUuid`, which survives edits; `_uuid` changes on every edit and would
  duplicate rows. `_submission_time` is UTC. `completion_seconds` is `end − start`, which
  the duration QA rules need.
- **A login-free submission must carry a valid portal signature.** Anyone holding the
  public form link could otherwise submit for a guessed Sample_ID. A submission that is
  neither signed by the portal nor made by a logged-in Kobo user is set aside and
  audited, never matched.
- **Full payloads are private.** They are written under `PRIVATE_DATA_ROOT`, outside
  anything nginx serves (`/media/` returns 404), and are included in backups.
- **Submissions move the case.** Submitted → S08; the QA decision moves it to S09 QA
  query or S10 QA passed.
- Admins can also trigger a pull on demand from the **"KoboToolbox sync"** panel on the
  QA queue screen (`/admin/qa`) instead of waiting for the next scheduled tick.

**Three forms are connected** (`apps/kobo/submission_copies.py` `FORMS`). Each role sees
only its own form:

| Form | Setting | Matched on | Roles |
|---|---|---|---|
| Main Study Questionnaire | `KOBO_ASSET_UID` | `SAMPLE_ID_FINAL` → Sample_ID | PI, Field Coordinator, QUAN QA RA, Supervisor |
| Main Study KII Guide | `KOBO_KII_ASSET_UID` | `part_a/KII_ID` | PI, Field Coordinator, KII RA, Supervisor |
| Document, Digital Platform & Media Analysis Tool | `KOBO_DOCUMENTS_ASSET_UID` | `section_a/DOC_ID` | PI, Field Coordinator, Documentary RA, Supervisor |

- **Form PDFs** (`/admin/submissions`): lists the completed forms newest first. Any of
  them can be downloaded as a readable PDF (sections, choice labels, repeats), or emailed
  to yourself or to the respondent. Every email is audited with the address masked.
- **On record pages:** the same PDFs appear on the matching case, KII and document pages.
- **Analysis packs** (`/admin/export` → *Analysis packs*, PI only, audited;
  `kobo/analysis-packs/{smartpls|atlas-kii|atlas-documents}/`, `apps/kobo/analysis_packs.py`). ZIPs that open
  directly in the analysis software, built from the deployed forms and live KoboToolbox data:
  - **SmartPLS 4**: `data.csv`/`data.xlsx` with one row per respondent who passed QA (`?include=all` adds the
    rest), numeric only, `-99` for missing, yes/no as 1/0, other single choice numbered in form order with
    'not applicable / not sure / prefer not' as missing, multiple choice as 0/1 columns; `data_dictionary.csv`;
    `README.txt`; and `PRIVATE_do_not_share/respondent_key.csv` linking row numbers to Sample IDs. No ids, free
    text or contact data in the data files; withdrawn participants left out.
  - **ATLAS.ti interviews**: one Word document per consenting, non-withdrawn interview (each question a
    heading, the answer beneath) plus `kii_attributes.xlsx`. Organisation, title, interviewer code, consent and
    contact fields are left out. Transcripts are not held by the portal and are added by the analyst.
  - **ATLAS.ti documents**: the uploaded source files named `DOC-ID_short-title` plus
    `documents_attributes.xlsx`.
- **PI data exports** (`/admin/export` → *KoboToolbox data*, PI only, audited). Two
  downloads per form:
  - **Excel workbook** (`kobo/forms/<key>/export/xlsx/`):
    - `README`;
    - `data_codes`: answers as stored codes, for SPSS, Stata or R;
    - `data_labels`: the same rows with choice labels;
    - one `repeat_N` sheet per repeat group, linked by `_parent_id`;
    - `questions` (the data dictionary) and `choices`;
    - for the questionnaire, `portal_*` columns: matched case, QA status, consent
      withdrawn, workflow status.

    Answers beginning `= + - @` are stored as text, so a spreadsheet never runs them as
    formulas.
  - **All completed forms as PDFs** (`kobo/forms/<key>/export/pdfs/`): a ZIP streamed as
    it is built, with `manifest.csv`.

  The frontend proxy streams the bytes through unchanged.
- **All three forms are synced into the portal** (`apps/kobo/form_sync.py`). Every 15 minutes
  (the same pass as questionnaire reconciliation), and on **Sync now** on the *Completed forms*
  page (`/admin/submissions`), the portal pulls the Questionnaire, the KII Guide and the Document
  Analysis Tool and keeps its own copy (`KoboFormSubmission`) with a content hash per submission.
  An edited submission is recognised by its changed hash; one deleted in KoboToolbox is flagged
  (`removed_at`), never silently kept. The page shows *KoboToolbox holds N · the portal holds N*
  and whether they agree (`GET /kobo/sync/status/`), and each listed row says whether the
  portal's copy is identical. What a sync also does: a completed KII Guide for a KII ID marks
  that interview's coding COMPLETE; a document coding submitted from the portal and later
  deleted in KoboToolbox unlocks the document, so it can be coded again. Submitting an AI draft
  refreshes the Document form's copy straight away.
- **Connecting or reconnecting Kobo:** `sudo bash /srv/agribiz-drp/deploy/configure-kobo.sh`
  sets the token, asset UIDs, form URL and webhook without echoing secrets.
- **Document analysis on the platform, not by hand.** A document's page
  (`/admin/documents/[id]`) has a **Code this document** link (`KOBO_DOCUMENTS_FORM_URL`,
  `apps/evidence/services.py build_document_coding_url`) that opens the Document Analysis
  Tool with the record's DOC-ID, title, author and source already filled in — a
  Documentary RA never retypes them, so the completed form is guaranteed to match back up
  with the right record. The page also stores the source file itself (a scan, a platform
  screenshot, a recording — up to `DOCUMENT_MAX_UPLOAD_MB`, default 60 MB) under
  `PRIVATE_DATA_ROOT`, downloadable only by roles with document access; uploading replaces
  any earlier file for that record. Every upload and download is audited.
  **Remove file** (next to the file name, with a confirmation) deletes a wrongly attached
  file from the server and clears its details; the removal is audited with the file name.
  An AI draft made from a file that is removed or replaced is discarded with it, so a draft
  of the wrong document can't be reviewed and submitted for the right one — unless it was
  already submitted to KoboToolbox, in which case it is kept as the record of what was filed.
- **AI-assisted coding, always reviewed by a person before it reaches KoboToolbox.**
  Sections B–L of the Document Analysis Tool are the study's actual documentary-analysis
  method — evidence-strength ratings, hypothesis-support codes, authenticity calls — so
  **Auto-fill** (`/admin/documents/[id]/ai-draft`, next to Code this document) never
  submits anything on its own. It has Claude read the uploaded source file
  (`apps/evidence/ai_coding.py`, `ANTHROPIC_API_KEY`) and draft an answer for every field,
  grounded in the document with page/paragraph locators. A Documentary RA reviews the
  draft in the portal, corrects anything wrong, and only then clicks **Submit to
  KoboToolbox**, which posts the reviewed answers as a completed record via the OpenRosa
  submission API (`apps/evidence/kobo_submit.py`). Deterministic fields (DOC-ID, title,
  author, date, source) are always taken from the document record itself, never from the
  model. Every draft and submission is audited, so the methodology write-up can state
  exactly which records were AI-assisted.
  - **A real platform quirk, found and fixed:** this KoboToolbox deployment's OpenRosa
    submission endpoint routes a submission by the root XML element's `id` matching the
    **asset UID**, not the XLSForm's `id_string` the ODK/OpenRosa spec would suggest —
    confirmed live against the actual project (two test submissions created under a
    `TEST-DELETE-ME` DOC-ID, verified, then deleted; 0 submissions before and after).
- **The KII Guide has the same prefilled launch link, deliberately narrower.** A KII
  record's page (`/admin/kii/[id]`) has a **Continue this interview** link
  (`KOBO_KII_FORM_URL`, `apps/kii/services.py build_kii_coding_url`) prefilled with the
  record's KII-ID. Unlike a document, a KIIRecord identifies a real person: the link never
  carries `participant_name`/role/organisation, only the system-generated ID and the
  interviewer's own username, and it is withheld entirely — not just hidden, refused
  server-side too — until participation consent is GIVEN.

### 4. QA and the Research Operations Centre (`/admin/*`, screens A01–A12)

Internal staff sign in at `/admin/login` (JWT-based, httpOnly cookies — the token itself
is never exposed to client-side JavaScript; see [Authentication](#authentication)).
There are **eight roles**, and each internal endpoint checks a specific one, never just
"is logged in."

**Navigation is scoped to the role.** `backend/api/navigation.py` is the single source of
truth for role → screens, served to the frontend by `GET /api/v1/auth/me/`. The nav bar
renders exactly that list — it is not a full menu with some entries disabled — and each
role lands on its own first screen at sign-in. A screen outside your role renders an
explicit "not part of your role" card rather than a page whose every fetch 403s. This is
UX only; the permission classes remain the real boundary.

| Role | Screens | Lands on |
|---|---|---|
| PI / Admin | 19 (everything) | `/admin/dashboard` |
| Field Coordinator | 18 (no Audit Log) | `/admin/dashboard` |
| Supervisor (read-only) | 17 (no Audit Log or Export) | `/admin/dashboard` |
| Analyst (read-only) | 7 (Executive, Sampling, Reports, Contact, KII/Doc dashboards, Cost, Export) | `/admin/dashboard` |
| Contact RA | 3 (Main-400 Register, Appointments, Follow-ups) — only its assigned cases | `/admin/sample` |
| QUAN/Kobo QA RA | 4 (QA Dashboard, Form PDFs, QA Queue, QA Exceptions) | `/admin/dashboard/qa` |
| KII RA | 3 (KII/Doc Dashboard, Form PDFs, KII Register) | `/admin/dashboard/kii-documents` |
| Documentary RA | 3 (KII/Doc Dashboard, Form PDFs, Documents) | `/admin/dashboard/kii-documents` |

The three RA roles are deliberately **not** interchangeable — see
[Notable fixes](#notable-fixes) for the over-grant this replaced. Read-only roles see
figures and lists on mixed screens but not the forms or buttons
(`components/admin/RoleGate.tsx`).

| Screen | Route | Purpose |
|---|---|---|
| A01 | `/admin/login` | Internal sign-in |
| A02 | `/admin/dashboard` | Executive dashboard — overall progress vs. the 400/60/50–75 targets, days to data lock, coverage gaps by stratum |
| — | `/admin/dashboard/sampling` | Main-400 by province, verified/total by stratum, reserve activations by reason |
| — | `/admin/dashboard/contact` | Organisations verified, invitations sent/opened, appointments, refusals |
| — | `/admin/dashboard/qa` | Submissions today/cumulative, QA queue depth, decisions recorded, administration-mode split |
| — | `/admin/dashboard/kii-documents` | KII and document progress vs. targets |
| — | `/admin/reports` | Fieldwork analytics: KPIs, response funnel, workflow, submissions per day, breakdowns by province/actor family/size with invited-vs-submitted share, administration modes with an imbalance alert, completion-time histogram, QA outcomes and flags, contact, KII and document progress. 7/30/90-day or all-time range; every chart has a table view |
| — | `/admin/organisations` | Register an organisation and create its sample case |
| A03 | `/admin/sample` | Main-400 / Reserve register, with bulk verification (move every Main case at S00, S01 or S02 one step forward at once, each move audited) |
| A04 | `/admin/sample/[sampleId]` | Case detail: assigned Contact RA, respondents and contact details, matched Reserve, PROIT pre-profile, invitations (sent with a ready-written message by WhatsApp, SMS or email, including email from the study address), workflow transitions, contact-attempt log, withdrawal, and the completed questionnaire PDF |
| A05 | `/admin/appointments` | Appointment queue with status transition buttons |
| — | `/admin/follow-ups` | Reminders due now from the approved reminder schedule, each with a one-tap WhatsApp link and "Mark as sent"; a Contact RA sees only its own cases |
| — | `/admin/submissions` | Completed forms: your role's KoboToolbox form, sync status and **Sync now**, download PDFs or email; PI also gets the Excel workbook and PDF ZIP |
| A06 | `/admin/qa` | QUAN QA decision queue (accept / re-query / reject) plus the KoboToolbox sync panel |
| — | `/admin/qa/exceptions` | QA exceptions raised by the rules: assign, work, then resolve or dismiss with a note |
| A07 | `/admin/kii`, `/admin/kii/new`, `/admin/kii/[id]` | KII register, creation, and per-record status/consent/transcript/coding workflow; **Continue this interview** opens the KoboToolbox KII Guide prefilled with the record's KII-ID, offered only once participation consent is GIVEN |
| A08 | `/admin/documents`, `/admin/documents/new`, `/admin/documents/[id]`, `/admin/documents/[id]/ai-draft` | Documentary evidence corpus, authenticity assessment gate before a document can be included; upload the source file, open KoboToolbox's Document Analysis Tool prefilled with the record's DOC-ID via **Code this document**; or **Auto-fill** to have AI draft the whole form for review before a human submits it |
| A09 | `/admin/reserve` | Reserve activation (five authorised reasons, mandatory evidence note) |
| A10 | `/admin/cost` | Fieldwork cost dashboard and entry form |
| A11 | `/admin/audit` | Full audit log — every sensitive action, correctly attributed to the admin who performed it |
| A12 | `/admin/export` | De-identified analysis export, full operational export (CSV), and (PI only) the SmartPLS 4 / ATLAS.ti analysis packs and each KoboToolbox form's full data workbook and PDF ZIP |
| — | `/admin/proit/[id]` | Researcher pre-profile review and lock (see [PROIT](#proit--pre-interview-profiling)) |
| — | `/admin/account` | Change your own password (available to every role) |

Every register screen (`/admin/sample`, `/admin/organisations`, `/admin/kii`,
`/admin/documents`, `/admin/appointments`, `/admin/reserve`, `/admin/audit`) paginates at
20 rows with Previous/Next controls, and most carry a `?search=` box wired to DRF's
`SearchFilter`. Before Sep 2026 none of them had either, so with 400 Main cases loaded
every row past the first twenty was unreachable from the UI.

Human QA decisions (accept / re-query / reject) always require a note and are the only
way a submission reaches `QA_PASSED` — there is no automatic pass path. A KII cannot be
marked completed with a recording unless **recording consent** was captured as its own,
separate decision from participation consent (never inferred from it).

### PROIT — pre-interview profiling

PROIT (Pre-Interview Respondent & Organisation Intelligence and Verification Tool,
`backend/apps/proit/`, spec in `docs/30_PROIT_MODULE.md`) shortens the interview by
establishing publicly available background facts *before* contact, so the respondent
confirms or corrects them rather than answering from zero.

- A researcher records each fact with its source, date, locator and confidence
  (HIGH/MODERATE/LOW), drawing on a four-tier source-authority hierarchy — statutory
  registers, then official reports, then reputable media, then corroborated public
  content. Evidence records carry `EVID-<5>` identifiers.
- A second researcher reviews and **locks** the profile (`/admin/proit/[id]`) before the
  respondent is contacted.
- Three values stay permanently separate and are never merged: the documentary value, the
  respondent's own answer, and the researcher's reconciled value.
- On the KII side an **adaptive gap engine** generates interview questions only for what
  is still genuinely unresolved.
- It can never pre-fill, skip or infer any frozen ABI/NFM/Digital-Readiness/FST scale
  item — only non-core descriptive background.

Respondent-facing PROIT is gated behind `PROIT_ENABLED_FOR_RESPONDENTS`, currently on.
It was first switched on (12 Sep 2026) on the PI's documented risk acceptance. On 15 Sep
2026 the PI confirmed in writing that PROIT is covered by his CUT student research
clearance. `docs/30_PROIT_MODULE.md` records both as the PI's statements.

### Research Clearance — verifying the study is genuine

`backend/apps/clearance/` lets the PI publish the study's official approval letters
(ethics clearance, institutional approval, supervision confirmation, introduction
letters) so a respondent can check the study is real before answering anything.

- **`/admin/clearance` (PI only).** Add a document's title, issuing body, type, reference
  number and a plain-language description, then upload its file (PDF/JPG/PNG, 20MB max).
  Two independent switches, both off by default: `active` and **Shown to respondents**
  (`is_public`). A document needs a file and `is_public` on before any respondent sees it.
- **Respondent-facing, token-gated.** The information step (R05 above) renders a "How to
  verify this is a genuine study" section listing every public, active document with a
  link to open its file — nothing at all if none is published, so an unconfigured study
  doesn't show an empty box. The file is served through the same private-storage pattern
  as documentary evidence: never web-served directly, only through a permission-checked,
  audited view. The response carries no case or respondent data.
- **Once shown, never silently deletable.** A document that was ever public — or whose
  file a respondent actually opened — can't be deleted via the API, even after being
  switched back off; the admin UI disables the button, but the server is the actual
  boundary. Retiring one means switching `is_public`/`active` off, not erasing the record
  of what respondents were shown.
- Deployed 1 Oct 2026; see `docs/27_AGENT_EXECUTION_PLAN.md`'s "Research Clearance screen"
  section for the build record, including an open question about which supervision
  letter(s) to publish.

### Contact, reminders and withdrawal

- **Assignment and verification.** Main cases are assigned to a Contact RA from the case
  page. A Contact RA sees only its own cases. Coordinators move cases through
  verification (S00 → S03) in bulk from the register. Bulk moves stop at S03: invitation
  and later statuses follow real events only.
- **Respondents and contact details.** The case page's *Respondents and contact details*
  panel records the respondent's name, role, phone, WhatsApp and email.
- **Invitations.** Issuing an invitation moves the case to S05 and shows a ready-to-send
  WhatsApp message and copy button with the personal link and manual code. Reissuing
  expires every earlier link that has not yet been submitted.
- **Case status follows the respondent.** Invitation opened → S06, survey started → S07,
  submitted → S08.
- **Follow-ups** (`/admin/follow-ups`). Reminders fall due on the approved schedule.
  Until WhatsApp Business Platform is set up, a person sends each one with a
  pre-written WhatsApp link and marks it sent, and who sent it is recorded. A case can
  only become **S13 Nonresponse** once every reminder was actually delivered.
- **Communications** (`/admin/communications`, 12 Oct 2026). Every message to and from
  participants in one place: WhatsApp, SMS and email the portal sent, with delivery ticks
  (sent, delivered, read, not delivered with the reason in plain words); WhatsApp messages
  received; email replies read from the study mailbox; and the events around them
  (invitations, those sent by hand from the study phone, the link opened, consent, the
  questionnaire submitted, follow-ups and calls). People write back from the same screen on
  any channel the rules allow. A Contact RA sees their own cases, a KII RA the KII records,
  the Supervisor reads. Replaced the WhatsApp-only Conversations screen.
- **Withdrawal** (case page). One action records a WITHDRAWN consent and revokes live
  invitations, which stops reminders. Where the workflow allows, it moves the case to
  S12, erases the respondent's contact fields and writes an audit entry. Answers already
  submitted are kept but never analysed (PI decision, 15 Sep 2026): left out of the
  analysis export, flagged `consent_withdrawn` in the operational export, and marked in
  the PI's KoboToolbox workbook and PDF ZIP.
- **Staff accounts and case assignment.**
  - `manage.py create_staff_accounts --file docs/templates/ABF-FST_Staff_Accounts_Template.xlsx
    [--assign-cases] [--dry-run]` creates named accounts from the PI's spreadsheet. The
    temporary passwords are written to a private file.
  - With `--assign-cases` it shares the shared account's Main cases evenly among the
    Contact RAs covering each province.
  - **Reassign cases** on the register (`POST /sample-cases/bulk-assign/`) moves cases by
    current owner, province and count. Every move is audited.

### 5. Exports and the audit trail

Two CSV exports exist, with a deliberately different schema:

- **De-identified analysis export** (`/admin/export` → "Download analysis export") —
  `sample_id, master_id, province, actor_family, value_chain, size_class,
  administration_mode, qa_status, submitted_at, completion_seconds`. No name, phone,
  email or gatekeeper field ever appears here, and participants who withdrew are left
  out. Safe to share with the wider research team.
- **Full operational export** — every submission, the same columns plus
  `consent_withdrawn, organisation_name,
  respondent_full_name, respondent_phone, respondent_email, gatekeeper_name,
  gatekeeper_contact`. Internal fieldwork operations use only, PI/Admin role required.
- **KoboToolbox data** (PI only): the answers themselves. For each of the three forms
  there is an analysis-ready Excel workbook (codes, labels, repeats, data dictionary) and
  a ZIP of every completed form as a PDF. See
  [KoboToolbox integration](#3-kobotoolbox-integration-the-actual-questionnaire).

Every sensitive action — consent recorded, invitation issued, reserve activated, KII
status changed, document authenticity/QA decision, a rejected invalid workflow
transition — writes an `AuditEvent` row visible at `/admin/audit`, correctly attributed
to the signed-in user who performed it (see [Notable fixes](#notable-fixes)).

### Authentication

Login (`POST /api/auth/login`, a Next.js route) exchanges credentials for a JWT via
Django's `/api/v1/auth/token/`, then sets it as an **httpOnly cookie** — the token value
never reaches client-side JavaScript. Every subsequent internal API call goes through
`/api/proxy/[...path]` (also a Next.js route), which reads the cookie server-side and
attaches the `Authorization: Bearer` header before forwarding to Django. The frontend
component code never handles a raw token.

---

## Architecture at a glance

```
Browser
  │
  ▼
Nginx  (research.agribizframework.com, TLS via Certbot)
  ├── /api/v1/, /api/schema/, /api/docs/   → Django + gunicorn (127.0.0.1:8100)
  ├── /django-admin/                        → Django + gunicorn (127.0.0.1:8100)
  ├── /static/                              → served from disk  (/media/ → 404: payloads are private)
  ├── /api/auth/*, /api/proxy/*             → Next.js (127.0.0.1:3100)  ← Next's own routes, NOT Django
  └── /  (everything else)                  → Next.js (127.0.0.1:3100)
```

- **Backend**: Django 5.1 + Django REST Framework, Python 3.12, PostgreSQL, 15 apps
  (`accounts, sampling, contacts, consent, invitations, kobo, messaging, kii, evidence,
  qa, dashboards, costs, audit, proit, clearance`).
- **Frontend**: Next.js 15 (App Router) + TypeScript, Tailwind, TanStack Query (30 s
  stale time, no retry on refusals), recharts for Reports.
- **Background jobs**: Celery + Redis, for Kobo reconciliation and the reminder queue
  (`--pool=solo --concurrency=1` in production — the VPS shares its memory budget with a
  sibling project, `docs/27_AGENT_EXECUTION_PLAN.md` Phase 10).
- **Same VPS, separate app**: shares infrastructure with the sibling ABI project
  (`docs/20_EMBEDDING_WITH_ABI.md`) but a completely separate database, Nginx
  `server{}` block, and systemd units — no shared code, no navigational link between
  the two.

---

## Quick start (local development)

Backend (Django + DRF, needs PostgreSQL 16+):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env                              # edit DATABASE_URL, KOBO_* etc. -- see below
python manage.py migrate
python manage.py seed_drp_dev                      # dev fixtures: strata, synthetic cases, one account per role
python manage.py runserver
```

Frontend (Next.js 15 + TypeScript, needs the backend running):

```bash
cd frontend
npm install
cp .env.example .env                               # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

Then open `http://localhost:3000` for the respondent-facing flow, or
`http://localhost:3000/admin` for the Research Operations Centre. `seed_drp_dev` prints
its credentials to the console: `e2e_admin` (PI/Admin) plus one `e2e_<role>` account for
each of the other seven roles, all sharing the same password. Signing in as each is the
quickest way to see the role-scoped navigation described above.

Background jobs (optional for most local work — only needed to actually exercise Kobo
reconciliation or the reminder queue):

```bash
# needs Redis running locally
cd backend
celery -A config worker --loglevel=info --pool=solo
celery -A config beat --loglevel=info
```

## Environment variables

**Backend** (`backend/.env`, see `backend/.env.example` for the full template):

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` locally, `config.settings.prod` in production |
| `DJANGO_SECRET_KEY` | Django's cryptographic signing key |
| `DJANGO_DEBUG` | Must be `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed `Host` headers |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `JWT_SIGNING_KEY`, `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`, `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Auth token config |
| `INVITATION_TOKEN_BYTES`, `INVITATION_TOKEN_EXPIRY_DAYS` | Invitation token generation |
| `KOBO_API_BASE_URL` | Kobo server, e.g. `https://kf.kobotoolbox.org` |
| `KOBO_API_TOKEN` | Kobo API token — **server-side only, never sent to the frontend** |
| `KOBO_ASSET_UID` | The Main Study Questionnaire asset UID |
| `KOBO_FORM_URL` | The questionnaire's public web-form link (`https://ee.kobotoolbox.org/x/…`) that respondents are sent to |
| `KOBO_KII_ASSET_UID`, `KOBO_DOCUMENTS_ASSET_UID` | KII Guide and Document Analysis Tool assets (Form PDFs, PI data exports) |
| `KOBO_DOCUMENTS_FORM_URL` | Document Analysis Tool's public web-form link — powers the document page's **Code this document** prefilled link |
| `KOBO_KII_FORM_URL` | Main Study KII Guide's public web-form link — powers the KII page's **Continue this interview** prefilled link, offered only once participation consent is GIVEN |
| `ANTHROPIC_API_KEY`, `AI_DOCUMENT_CODING_MODEL` | AI-assisted document coding drafts (`deploy/configure-ai-coding.sh`); blank key = the **Auto-fill** button doesn't appear. Paid, per-request cost to the PI's own Anthropic account |
| `KOBO_OPENROSA_BASE_URL`, `KOBO_ACCOUNT_USERNAME` | Where a reviewed AI draft is submitted to KoboToolbox (`deploy/configure-ai-coding.sh`) — a different host and mechanism from the `kf.` API v2 used everywhere else |
| `KOBO_WEBHOOK_SHARED_SECRET` | Validates `POST /api/v1/kobo/webhook/`; also signs the portal token passed to the form |
| `KOBO_RECONCILIATION_INTERVAL_MINUTES` | Celery Beat pull frequency |
| `PRIVATE_DATA_ROOT` | Where full Kobo payloads and uploaded document source files are stored; must not be under anything nginx serves |
| `DOCUMENT_MAX_UPLOAD_MB` | Size limit for an uploaded document source file (default 60; nginx's `client_max_body_size` must allow it) |
| `PROIT_ENABLED_FOR_RESPONDENTS` | Shows the PROIT verification step to respondents |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `STUDY_REPLY_TO_EMAIL` | Outgoing mail for emailed form PDFs, sent as abffst.research@gmail.com with a Gmail App Password; set with `deploy/configure-email.sh` |
| `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PORT`, `EMAIL_INBOX_FOLDER`, `EMAIL_SENT_FOLDER`, `EMAIL_INBOX_POLL_MINUTES`, `EMAIL_INBOX_BACKFILL_DAYS`, `EMAIL_INBOX_MAX_PER_RUN` | Reading replies from the study mailbox into Communications (blank host = off; read-only; only mail from or to an address on a record is copied); set with `deploy/configure-email-inbox.sh` |
| `COMMUNICATION_BLOCKED_PHRASES`, `COMMUNICATION_MAX_LENGTH` | Words a message written in Communications may never contain (AGENTS.md rule 2), and its maximum length |
| `LOGIN_THROTTLE_RATE`, `RESPONDENT_THROTTLE_RATE` | Sign-in and respondent-flow rate limits (defaults 30/min and 120/min) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM` | SMS and WhatsApp through Twilio (optional; each channel is offered only once its own values are set); set with `deploy/configure-twilio.sh` |
| `TWILIO_WA_CONTENT_INVITATION`, `TWILIO_WA_CONTENT_KII_INVITATION`, `TWILIO_WA_CONTENT_REMINDER_DAY2`, `TWILIO_WA_CONTENT_REMINDER_DAY7` | Meta-approved WhatsApp templates (Twilio Content `HX…` ids); invitation variables `{{1}}` who it is for, `{{2}}` link, `{{3}}` valid-until date, `{{4}}` code |
| `TWILIO_WA_CONTENT_INTRO`, `TWILIO_WA_CONTENT_INTRO_REMINDER`, `OUTREACH_REMINDER_DAYS`, `OUTREACH_GIVE_UP_DAYS`, `OUTREACH_YES_WORDS`, `OUTREACH_NO_WORDS` | "Ask first" introductions: the Meta-approved introduction and reminder templates (`{{1}}` organisation, quick-reply payloads YES / NO), days before the one reminder (3) and before listing for a phone call (4), and the whole-message words read as YES or NO. Replies reach `POST /api/v1/twilio/inbound/`, set as the WhatsApp sender's incoming-message webhook |
| `TWILIO_SMS_DAILY_MAX`, `TWILIO_WHATSAPP_DAILY_MAX`, `TWILIO_SMS_SEGMENT_PRICE_USD`, `TWILIO_SMS_OPT_OUT_LINE` | Daily caps (150 / 250, invitations and automatic reminders together), the price used for the batch cost estimate (US$0.3212 per segment to Zimbabwe, checked 2026-10-07), and an optional PI-approved line added to every SMS (two-way SMS is not available in Zimbabwe, so nobody can reply STOP) |
| `CELERY_BROKER_URL` | Redis URL |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Must match the deployed frontend origin exactly |
| `BACKUP_RPO_HOURS`, `BACKUP_RTO_HOURS` | Documented targets for `deploy/backup.sh` |

**Frontend** (`frontend/.env`, see `frontend/.env.example`):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_APP_DOMAIN` | The deployed domain |
| `NEXT_PUBLIC_API_BASE_URL` | Where the frontend's own `/api/proxy` route forwards to (Django's `/api/v1`) |
| `NEXT_PUBLIC_APP_ENV` | `development` / `production` |

Never commit real values for any of the above — both `.env` files are gitignored, and
`*.env.production` is gitignored too.

## Tests

```bash
cd backend  && pytest              # 458 tests: unit, API, privacy, roles, gates, Kobo, exports, query counts
cd backend  && ruff check .        # linting
cd frontend && npx tsc --noEmit    # type checking
cd frontend && npm run lint        # eslint
cd frontend && npm run test        # Vitest component tests
cd frontend && npx playwright test # E2E: 43 pass, 2 skipped on purpose -- see below
```

The Playwright suite covers:

- **Respondent flow:** invitation → consent → Kobo redirect, its failure branches, and
  a poor-connection phone run.
- **Invariants:** privacy and the reserve lock.
- **Every screen for every role:** `all-screens-audit` at 1366px and 375px, failing on
  server errors, refused calls, crashes, endless loading or sideways scrolling.
- **Every admin panel:**
  - workflow transitions and contact attempts, respondents and contact details,
    withdrawal, and Follow-ups;
  - appointment status and the cost-entry form;
  - the KII recording-consent gate and the document authenticity-before-inclusion gate;
  - reserve activation, Reports, and the Kobo sync panel;
  - Form PDF downloads (checked byte for byte) and the PI's workbook/ZIP downloads.

**Backend checks beyond the functional tests:**

- `tests/test_query_counts.py` fails if a register, export or Follow-ups query starts
  growing with the data.
- On a server, `python manage.py golive_preflight` exercises the go-live checklist
  inside a rolled-back transaction.

Two things worth knowing before adding tests here:

- `manage.py seed_drp_dev` creates **one account per role** (`e2e_admin`, plus
  `e2e_<role>` for the other seven, same password), which is what
  `e2e/role-scoped-navigation.spec.ts` signs in as. Fixtures that tests mutate (workflow
  status, reserve activation) are force-reset on every seed run, so the suite stays
  reliable against a shared, never-reset local database.
- **A test asserting that a gate refuses something must not use the shared seed case.**
  Consent and eligibility both attach to the `SampleCase`, so by the second run it
  already has GIVEN consent and eligible respondents on it, and the refusal silently
  never fires. Use `issueTokenOnFreshCase()` from `e2e/helpers.ts`, which builds its own
  organisation and case. Two specs were caught passing for this reason.

Two tests skip on purpose rather than being absent:

- **`e2e/pi-blocked-items.spec.ts`:** the automatic WhatsApp Business Platform sending
  has no Meta account yet.
- **The Form PDF and PI download tests:** they skip when the environment cannot reach
  KoboToolbox.

Both skips appear with a written reason in every run's report.

A full manual QA pass (this hardening round) also walked every respondent-flow screen
and every admin screen in a real browser against a freshly seeded local database, and
separately against production — see [Notable fixes](#notable-fixes).

## Deployment

Production is `research.agribizframework.com`, a single VPS shared with the sibling ABI
project (own database, own Nginx `server{}` block, own systemd units — see
`docs/20_EMBEDDING_WITH_ABI.md`).

```bash
# On the server, as root, after copying the updated code to /srv/agribiz-drp/:
sudo bash /srv/agribiz-drp/deploy/deploy.sh
```

`deploy.sh` backs up the database, installs backend/frontend dependencies, runs
migrations, builds the frontend, restarts all four systemd units
(`drp-backend`, `drp-frontend`, `drp-celery-worker`, `drp-celery-beat`), validates the
Nginx config without overwriting Certbot's HTTPS block, and runs health checks against
the backend, frontend, and the full HTTPS path through Nginx — it fails loudly (and
tells you where to look) rather than reporting success on a partial deploy. To roll
back: `sudo bash /srv/agribiz-drp/deploy/rollback.sh`.

One-time configuration scripts, all run on the server as root. None of them echoes a
secret, so nothing sensitive needs pasting into chat or a ticket:

| Script | Sets up |
|---|---|
| `deploy/configure-kobo.sh` | KoboToolbox token, the three asset UIDs, form URL, webhook and its secret |
| `deploy/configure-email.sh` | Gmail SMTP for abffst.research@gmail.com (needs a Google App Password) |
| `deploy/configure-twilio.sh` | SMS and WhatsApp through Twilio: Account SID and Auth Token (hidden prompt), the SMS sender and WhatsApp sender, the four WhatsApp template ids; sends a test SMS to a number you type. Re-run to add the WhatsApp values once Meta approves them |
| `deploy/configure-ai-coding.sh` | AI-assisted document coding (needs an Anthropic API key with billing set up — a paid, per-request cost to the PI's own account) |
| `deploy/configure-offsite-backup.sh` | Encrypted offsite backups to Google Drive (rclone crypt, `drive.file` scope); prints the encryption key once, to store in a password manager |

Backups:

- **Local:** `drp-backup.timer` runs `deploy/backup.sh` every 4 hours (database plus
  private payloads).
- **Offsite:** `drp-offsite-backup.service` copies each backup to Google Drive once it
  is configured.

After a deploy, `cd /srv/agribiz-drp/backend && sudo -u agribiz-drp venv/bin/python
manage.py golive_preflight` checks the go-live path end to end without changing any data.

**Nginx routing** — the one part of this stack that is easy to get subtly wrong, since
Django and Next.js both technically live under `/api/` (see
[Notable fixes](#notable-fixes) for what happens if you don't
get this right):

```
/api/v1/, /api/schema/, /api/docs/   → Django   (gunicorn, 127.0.0.1:8100)
/django-admin/                        → Django   (gunicorn, 127.0.0.1:8100)
/static/                              → served from disk by Nginx directly
/media/                               → 404 (never serve Kobo payloads)
/api/auth/*, /api/proxy/*             → Next.js  (127.0.0.1:3100) -- NOT Django
/  (everything else)                  → Next.js  (127.0.0.1:3100)
```

### Production verification

After any deploy, confirm (not just "curl returns 200" — confirm the feature actually
works):

1. `https://research.agribizframework.com/` loads the public respondent landing page.
2. `https://research.agribizframework.com/admin/login` → sign in → the Executive
   Dashboard actually renders (not a permanent spinner, not a console 404 on
   `/api/auth/me` or `/api/proxy/...` — see the nginx note above).
3. `systemctl status drp-backend drp-frontend drp-celery-worker drp-celery-beat nginx`
   all report `active`.
4. `sudo journalctl -u drp-backend -n 50 --no-pager` has no repeating errors.
5. A test action (e.g. the "Sync now" Kobo panel on `/admin/qa`) round-trips through
   Nginx → Next.js *or* Django correctly depending on which route it hits.

### Troubleshooting

| Symptom | Likely cause | Where to look |
|---|---|---|
| Login succeeds but the dashboard never loads / spins forever | Nginx routing `/api/auth/` or `/api/proxy/` to Django instead of Next.js | `sudo journalctl -u drp-backend` for 404s on those exact paths; check `/etc/nginx/conf.d/research.agribizframework.conf` against the table above |
| "Sync now" always fails | The Kobo API token was rotated or expired, or an asset UID is wrong | The panel shows the actual Kobo API error; re-run `deploy/configure-kobo.sh` with the new token |
| Form PDFs says "isn't connected to KoboToolbox yet" | That form's asset UID is not set (`KOBO_KII_ASSET_UID` / `KOBO_DOCUMENTS_ASSET_UID`) | `deploy/configure-kobo.sh` |
| "Email" on a form PDF is missing or fails | SMTP not configured, or the Gmail App Password was revoked | `deploy/configure-email.sh`; `journalctl -u drp-backend` for the SMTP error |
| A submission appears in the audit log as not verified / not matched | Submitted through the public form link without the portal's signature, or with a Sample_ID the portal doesn't know | Expected protection; check the case and reissue the respondent's invitation |
| A downloaded PDF or workbook will not open | A proxy change reading the response as text instead of streaming bytes | `frontend/app/api/proxy/[...path]/route.ts`; `e2e/admin-form-pdfs.spec.ts` |
| A Contact RA sees an empty register | No cases assigned to that account | Case page → assigned Contact RA |
| An admin's actions show up as "system" in the audit log | Should not happen after this hardening pass (`apps/audit/middleware.py`) — if it recurs, check that `AuditContextMiddleware` is still listed in `MIDDLEWARE` in `config/settings/base.py` | `backend/tests/test_audit.py` |
| A workflow/appointment/contact-event admin action 400s | Check whether a serializer field that should be server-resolved (from the URL, or from the state machine) was accidentally made writable again | `backend/tests/test_sample_case_api_integrity.py`, `test_appointment_status.py`, `test_contact_event_api.py` |
| `npm ci` fails with `EACCES: mkdir '/home/agribiz-drp'` | The `agribiz-drp` system user has no writable `$HOME` for npm's cache | `deploy/setup-server.sh` creates this directory explicitly; re-run it, or `mkdir -p /home/agribiz-drp && chown agribiz-drp:agribiz-drp /home/agribiz-drp` |
| "Submit to KoboToolbox" returns `kobo_submission_rejected` (HTTP 404) | The submission's root XML element `id` doesn't match the asset UID -- this deployment routes by asset UID, not the XLSForm's `id_string` | `apps/evidence/kobo_submit.py`; should not recur, `test_root_element_id_is_the_asset_uid_not_the_form_id_string` pins it |
| "Auto-fill" doesn't appear on a document's page | `ANTHROPIC_API_KEY` isn't set | `deploy/configure-ai-coding.sh` |

## Notable fixes

### Long names no longer cost the introduction or the thank-you (21 Oct 2026)

Meta caps a WhatsApp template's body at 1,024 characters once its variables are filled in. Twilio accepts the request
and then fails the message with 63021 "Channel invalid content error", which looked like an ordinary delivery failure.
The PI's introductions are about 990 characters before the name goes in, and the thank-you letter is 994, which leaves 17
characters for a Main organisation and 7 for a KII informant. So introductions to long names ("SAMUSHA & NCUBE FARM
FRESH PRODUCE SUPPLIERS (PRIVATE) LIMITED") failed, and 4 of the first 5 WhatsApp thank-yous never arrived. Nobody
noticed because a failed template is recorded like any other failed delivery, and the email fallback (where there was
one) still sent something. `outbound.fit_template()` now shortens the greeted name only as far as the limit needs: first
the legal form goes, then the trading name alone is used ("... t/a Rainham Abattoir" -> "Rainham Abattoir"), then the
name is cut at a word, never leaving half a bracket. Introductions (Main and KII) and the thank-you use it. The limit is
`WHATSAPP_TEMPLATE_BODY_MAX`. A shorter thank-you template would let names through in full.

On 22 Oct the same limit showed that the approved KII v3 introduction (with the study letters) is 1,018 characters before
the name. That leaves room for 6 characters, so every KII introduction sent with it would have failed. None had been sent
yet: the SAFIRE director's was stopped by a length check. `outreach._intro_content()` now takes the first approved
template (letters, new wording, then the earlier one) that the greeting fits, at most with its legal form dropped. If it
fits none, the template with the most room is used and the name is cut at a word. KII introductions therefore go with
the earlier approved wording until a shorter v3 is approved.

### A business WhatsApp's automatic greeting no longer waits for a person (20 Oct 2026)

Many organisations' WhatsApp Business accounts answer every incoming message automatically: "Thank you for contacting
X! Please let us know how we can help you.", "We're unavailable right now, but will respond as soon as possible.",
"Welcome to X", "Follow our WhatsApp channel", a price list. Each one is a reply that is neither YES nor NO, so it was
stored as "anything else" and put on Communications under **Waiting**: on 20 Oct, 28 of the 41 waiting messages were
these, burying the real questions. Nobody noticed sooner because each looks like a reply, and only the count gave it
away. `outreach.is_auto_reply()` now recognises them from `OUTREACH_AUTO_REPLY_PATTERNS` (configurable regular
expressions, starting from the ones used in that day's one-off cleanup); such a message is stored as kind `AUTO`, is
not waiting, shows an **Auto-reply** label in the conversation, and gets nothing sent back. The introduction is left
open (Intro sent / Reminded), so its reminder still goes: a person has not answered yet. A message that also holds a
yes- or no-word, a phone number, a shared contact card, or a question other than "How can we help you?"
(`OUTREACH_AUTO_REPLY_QUESTION_PATTERNS`) is never taken for one and still waits. This applies to replies to an
introduction (Main-400 and KII); messages from other numbers wait as before.

### "Good day YES" is a YES (19 Oct 2026)

A reply to an "ask first" introduction counted as YES or NO only when the whole message was one word from
`OUTREACH_YES_WORDS` / `OUTREACH_NO_WORDS` (or the quick-reply button). An informant who typed "Good day YES" (KII-0181)
was classed as "anything else" and quietly left on Communications for a person, so no link went until the PI saw it and
sent it by hand. Nobody had noticed because a held reply looks the same as a genuine question: it raises no error, and
the button replies, which most people use, always worked. `classify()` now also accepts a short reply whose words are
yes-words only (or no-words only) plus greetings and courtesies from `OUTREACH_REPLY_COURTESY_WORDS` (English, Shona,
Ndebele; configurable). A question mark, yes and no together, or any other word -- "no problem", "Yes, I'll take part",
"Let me give you the number of..." -- still goes to a person. Thank-you buttons are still checked first.

### The study's clearance letters go with the invitation (19 Oct 2026)

The ethics clearance and ministry letters were shown only on the information page of a participant's link, so someone
wary of an unknown message never saw them: a key informant left an invitation unanswered, then agreed to meet once
the PI sent him the letters. Emailed invitations (Main-400 and KII, and the email sent when WhatsApp cannot be
delivered) now attach every letter a participant may see -- public, active, with a file (`clearance.respondent_letters`)
-- and say so; a private or switched-off letter never goes. For WhatsApp, the same letters are combined into one PDF
(`letters_pack`) served at `/api/v1/study-letters/<STUDY_LETTERS_KEY>/ABF-FST-Study-Letters.pdf` for a template with
the PDF above the introduction; a wrong or missing key 404s.

### Cost register: what each cost was for, who was paid, and a table of every entry (18 Oct 2026)

The Cost Dashboard recorded a date, a category and an amount, and showed only totals by category: "Claude
subscription, $20" or "Allowance to <RA>, $30" could not be told apart from any other Software or RA-allowance spend,
and no single entry could be seen again. Each cost now records **what it was for** (required) and **who was paid**,
under categories that include Software / AI tools; `GET /api/v1/costs/` lists every entry newest first with the total
of what it lists (filter `?month=YYYY-MM`, `?category=`), and `/costs/<id>/` corrects or deletes one -- each audited
with what it was before (`cost.recorded`, `cost.updated`, `cost.deleted`). The Supervisor reads the entries; the
Analyst sees only the dashboard totals, since entries name the people paid. Manuals 1.45.

### Participants who complete are thanked, and asked whether they want the findings or a workshop invitation (18 Oct 2026)

At the PI's request (`apps/messaging/thanks.py`). A Main-400 or Reserve case whose questionnaire reached KoboToolbox
(its link SUBMITTED or QA_PASSED, or the case at S08-S11) and a KII record marked COMPLETED are thanked once: on
WhatsApp with the template `abffst_thank_you` (`TWILIO_WA_CONTENT_THANK_YOU`, used only once Meta approves it) to the
number the link went to, else by email with the PI's full letter. Never after consent was withdrawn, never a case
whose metadata `thank_you` says skip (the four possible test cases SID-2026-000001/02/05/62 are marked so until the
PI confirms them). The WhatsApp buttons (Findings & workshop / Findings only / Workshop only) and an email answer
starting BOTH, FINDINGS or WORKSHOP are recorded as `metadata["thank_you"]["preference"]` and audited; a button is
checked before YES/NO, so it can never be read as YES to an introduction. Runs every 30 minutes, 07:00-19:59
(Periodic task "Thank participants who completed").

### The PI's revised invitation wording; introductions switch to it once Meta approves (18 Oct 2026)

The PI rewrote the study invitation (purpose, why participation matters, what it involves, voluntary participation,
the study's background site, and that a YES gives permission to send materials, not consent). Emailed invitations
(`build_messages`, `build_kii_messages`) now carry that text in full, with the personal link in place of "May I send
you the link?"; the two uses of "guarantee" in the draft became "promise", as AGENTS.md rule 2 requires. WhatsApp
caps a template at 1,024 characters, so a condensed version was submitted to Meta as `abffst_intro_v2` and
`abffst_kii_intro_v2`, replaced the same day by the PI's corrected `abffst_intro_v3` / `abffst_kii_intro_v3` (migration 0019) (`TWILIO_WA_CONTENT_INTRO_NEXT` / `_KII_INTRO_NEXT`; wording copy in migration 0017).
`outreach._intro_content` sends the new template only once Meta's status for it is a definite "approved"
(`twilio_client.content_approved`), else the current one -- so the switch needs no one to make it, and an
unapproved template is never used (Twilio would accept it and fail it later, 63016).

### Long WhatsApp and SMS messages go as numbered parts; replies get the refused-words check (17 Oct 2026)

Twilio refuses a WhatsApp or SMS body over 1,600 characters, while Communications allowed 3,000. On 17 Oct the PI's
2,600-character study background to a new contact was refused with "The concatenated message body exceeds the 1600
character limit". A written message over `COMMUNICATION_TEXT_PART_MAX` (1,500) is now cut at paragraph, then sentence,
breaks into numbered parts, "(1/2) ...", sent in order (`outbound.split_text` / `send_text`); if a later part fails the
writer is told which parts went. Both the reply box and the reply to an unknown number show how many messages a text
will go as. The same message showed a second gap: the conversation reply (`outreach.reply_from_inbox`) had neither the
3,000-character limit nor the check that refuses words respondents must never see (AGENTS.md rule 2) -- that text held
"guarantee" and reached Twilio, refused only for its length. Unnoticed because every reply until then was short. The
reply now applies both, as Communications does.

### "Ask first" uses a case's untried mobile, not the one that already failed (17 Oct 2026)

The introduction always went to a case's first mobile (`outreach._mobile`), and a KII record's first (`_kii_mobile`).
Once that number had failed (not delivered, or no reply after the reminder) the portal refused the case as "already
asked" -- even when a new number had since been added. On 17 Oct a contacts import added new numbers to six Main cases
whose first number had failed; the batch and the send button both picked the old number and refused, and the six were
introduced by hand. Unnoticed because until then no import had added a second number to a case whose first had failed.
The number chosen is now the first mobile on file not already tried without success -- across every person on a case and
every number in a field -- and the introduction records that person, so its reminder goes to the same number. A case or
record is refused only when every mobile on it has failed. This also means a case whose field already held two mobiles
("0772 686106; 0773 626999") is asked on the second once the first fails.

### A KII record asked on two of its numbers is reminded on each (15 Oct 2026)

A KII introduction's reminder went to the record's first mobile, whichever number the introduction had gone to. On
15 Oct KII-0028's informant was asked on both his mobiles; the second one's reminder would have gone to the first
number, which would then have had two and the second none. Unnoticed because until then a KII record was only ever
asked on one number. The reminder now goes to the record's number that matches the introduction
(`outreach._asked_number`), as the Main-400 one already did.

### KII interview link pre-fills the organisation and, on the informant's own link, the interviewer code (15 Oct 2026)

The KII Guide's Part A requires an "Interviewer code" and the "Organisation represented". The portal's link
pre-filled only the KII ID, so an informant completing the interview alone -- on a phone -- was asked for an
interviewer code they could not have and had to leave the form to find their organisation; the first informant to
say yes (KII-0095) wrote back saying so. Unnoticed because every earlier KII interview was RA-administered, where
the interviewer knows both. `build_kii_coding_url()` now pre-fills `org_represented` on every link, and on the
informant's own link (`/kii-invitations/kobo-redirect-url/`) `interviewer_code=SELF` and today's date. Checked
against the live form: the three values land in the right fields. **Privacy change, at the PI's request:** the
organisation name now travels in the KoboToolbox URL; until then nothing but the KII ID did. The person's name and
role still never do (`test_coding_url_never_carries_participant_identity`).

### A KII informant can pass the study to someone else (15 Oct 2026)

The "passed us to someone else" referral (`outreach.refer_introduction`) was Main-400 only, so a KII reply such as
"Speak to Mr Parsons" plus a number (KII-0132) had no way to be asked. `outreach.refer_kii_introduction()` makes
the record that person -- a KII record is one informant -- puts their mobile in the WhatsApp field (the numbers
already on file stay), asks them first on their own number, and marks the earlier introduction REFERRED so its
reminder stops. Refused for a landline, a number already asked about the record, or a record already invited.

### "Ask first" batches skip records with no mobile before choosing (15 Oct 2026)

An "Ask first" batch picked its working list -- twice the number requested -- in register order and only then
dropped records with no mobile. On 15 Oct a KII batch of 72 met 87 landline-only records first, used up its list on
them, and sent 57; the other 15 were sent one by one. Unnoticed because the earlier Main-400 batches had few
landline-only cases near the front. Both the KII and the Main-400 batch now keep only records with a WhatsApp-capable
number before choosing (`apps/kii/batch.py`, `apps/invitations/batch.py`).

### Fact check saved in one call (14 Oct 2026)

The pre-interview fact-check pages (KII `/ki/[token]/verify` and Main-400 `/i/[token]/verify`) saved one answer per
request, while each personal link is limited to 20 requests a minute (`PerTokenThrottle`). Any profile with more than
about 18 facts therefore stopped part-way with "We've had a lot of requests from your connection" -- the PI's test of
KII-0001 (23 facts) saved 20 and stopped; 112 KII profiles were locked with up to 30 facts each. Unnoticed because the
test profiles had two or three facts. Both endpoints now take every answer in one call
(`{token, answers: [{field_id, status, respondent_value}, ...]}`, up to 200), saved together or not at all -- an
invalid answer is refused with its `field_id` and nothing is kept; another record's item still answers 404. The
one-field form still works.

### WhatsApp daily limit counted the way Meta counts it (14 Oct 2026)

The portal's WhatsApp cap counted every message sent since midnight -- replies on Communications and the link sent
after a YES included -- while Meta's limit counts different people started with a template in a rolling 24 hours. On
14 Oct the cap read 250 of 250 with about 163 people actually counted by Meta, and from then on a YES would not have
got its link. Now (`outbound.sent_today` / `daily_max`):

- only template messages (`ProviderMessage.is_template`: introductions, reminders, invitations sent first) count, one
  per person, over the last 24 hours; free-text replies inside a conversation are never counted or held back;
- the limit is the smaller of the study's ceiling (`TWILIO_WHATSAPP_DAILY_MAX`, now 500, PI decision) and Meta's
  current tier for the number, read from Twilio's Senders API (`twilio_client.meta_messaging_limit`, cached 30 min;
  the last value read, else 250, if Twilio can't be asked), so the portal follows Meta's upgrade to 2,000 by itself.

### No automatic answer to anything but YES or NO (14 Oct 2026)

PI decision: a WhatsApp message that is not a clear YES or NO -- a question, a greeting, a business's auto-reply, an
invitation code asking for a phone interview, a message from an unknown number -- waits on Communications for a person
and gets **no** automatic answer. Before, each got "Thank you for your message. A member of the research team will
reply..." (or the unknown-number / phone-request equivalent) once a day; on the first fresh-start day ten of those answers
went to businesses' own automatic replies. YES and NO are still acted on and acknowledged
automatically. `OUTREACH_AUTO_ANSWER_OTHER=True` brings the old behaviour back (AGENTS.md rule 7).

### "Passed us to someone else" (14 Oct 2026)

Several organisations answered the introduction by sharing a contact for the right person. `outreach.refer_introduction()`
adds that person to the case and asks them first on their own number; the organisation's introduction becomes
`REFERRED` ("Passed us to someone else") so its reminder stops, and the case is never re-asked on the organisation's
line by a later batch. Reminders and the SMS fallback now go to the number the introduction was actually sent to
(`_asked_number`: the outreach's own person), not the case's first number -- after a referral that would have been the
organisation. Refused for a landline, a number already asked about the case, or a case no longer waiting. Audited as
`outreach.referred`.

### WhatsApp voice notes, pictures and shared contacts; "wants to answer by phone" (14 Oct 2026)

Two gaps found answering the first fresh-start replies:

- **Media was thrown away.** The incoming-message webhook kept only the text, so a message that was only a voice note,
  picture or shared contact arrived empty -- Kushinga Phikelela shared "this person" to contact and nobody could see who.
  Now each attachment is listed from Twilio (`Messages/{sid}/Media`), copied into `PRIVATE_DATA_ROOT/whatsapp_media/`
  (never web-served; capped by `WHATSAPP_MEDIA_MAX_MB`), shown on Communications (voice notes play, pictures show, a
  vCard reads as name, number and email), opened only through `GET /api/v1/communications/attachments/{id}/` by people
  who may see that conversation (audited), and deleted on withdrawal. `InboundAttachment`, `apps/messaging/media.py`.
- **An invitation code looked like a stray word.** The invitation says "Prefer to answer by phone? Reply and quote code
  ABCD2345"; AfriGroup did ("CALCLWRI") and it sat among other messages. A reply containing a word that verifies against
  that case's or KII record's own code hash (or any code, for a number on no record -- which then finds its case) is now
  `ReplyKind.PHONE`, shown as "Wants to answer by phone: call them", audited `conversation.phone_requested`, and answered
  once a day (Message template `outreach_phone_requested`). A random 8-letter word is not taken as a code.

### WhatsApp first; without WhatsApp, email (14 Oct 2026)

PI decision: when an "ask first" introduction cannot be delivered -- the number is not on WhatsApp, Meta holds it
back, or the SMS fallback (where SMS is set up) also fails -- and an email is on file, the invitation goes by email
instead (`outreach.email_after_failed_intro`, run by the Celery worker so Twilio's status webhook is answered at once).
It is the ordinary invitation, issued and sent as one step by the batch's `send_one()` (a failed email keeps no link):
the Main case moves to S05, a KII record to INVITED, and either leaves the phone list. It keeps to the daily email
limit (audited `outreach.email_fallback_waiting` when reached) and never sends for a case invited, refused or completed
in the meantime. With no email, the case stays on the phone list as before.

### A number that never got the introduction is not asked again (14 Oct 2026)

On the first fresh-start day 171 introductions went out and 60 never arrived -- 51 to numbers not on WhatsApp (63024).
An introduction that is not delivered, or gets no answer after the reminder, leaves the case eligible for
"ask first" again (so a corrected number can be asked), and the batch panel immediately showed 48 cases "ready": the
next batch would have messaged the same dead numbers again, spending the daily limit and the new line's standing with
Meta. `outreach.tried_this_number()` now keeps a case or KII record out of introductions while its current mobile is
the one already tried; a corrected number can be asked. Those cases get an email invitation where there is an email,
and are otherwise on the phone list.

### Fresh start for Main-400 outreach on the new WhatsApp line (14 Oct 2026)

PI decision: with the study now sending from its own Twilio WhatsApp line, every Main case that was contacted but
never completed is asked again from the beginning ("ask first", then the link) instead of being reminded about an old
invitation. `manage.py fresh_start_outreach --reason "..." --user <pi> [--apply]` (dry run without `--apply`):

- **Reset:** Main cases at S04-S09 or S13 with **no questionnaire submission** go back to S03, every link they still hold
  is revoked (so no reminder about an old link goes out), and each is audited as `sampling.status_reset_fresh_start`.
- **Never touched:** cases with a submission (the 12 completed organisations), refusals (S12), unverified cases (S00-S02)
  and Reserve cases.
- **Kept:** respondents, consent records (a consent given stays given; the one online decline stays on file and the
  consent page asks again -- re-asking that person was the PI's explicit decision), messages and the audit trail.

### Ask first for KII informants (14 Oct 2026)

At the PI's request, KII informants can be asked first, as Main-400 organisations are: a short WhatsApp introduction
in the PI's own voice about a confidential key informant interview of about 30 minutes, with Yes / No buttons. The
reply decides the rest, with nobody touching the platform:

- **YES:** `issue_kii_invitation()` issues the link (PROSPECT -> INVITED) and its wording goes back in the same chat,
  in one transaction -- if it cannot be sent, no link is kept and a person follows up.
- **NO / STOP:** the record becomes DECLINED (as a decline on their own link does), any open link is revoked, one
  acknowledgement.
- **Anything else:** one automatic answer a day, and the message waits on Communications.
- **No reply:** one reminder after `OUTREACH_REMINDER_DAYS`, then the record is listed on the KII Register under
  "Asked, no reply: phone them" (`GET /api/v1/kii-outreach/unanswered/`). An undelivered WhatsApp introduction is
  re-sent once by SMS with the tap-to-reply link.

How: `Outreach` now belongs to exactly one Main case **or** one KII record (a database check constraint), and the
existing reply handling branches on which (`apps/messaging/outreach.py`). The KII introduction has its own templates
(`TWILIO_WA_CONTENT_KII_INTRO`, `_REMINDER`, created and submitted to Meta on 14 Oct; wording also in Message templates
for the SMS fallback). One record at a time from the record page (`/api/v1/kii-outreach/`, PI / FC / KII RA), or as
the "Ask first" mode of **Send KII invitations** (PI / FC). A reply from a number asked twice -- a Main case and a KII
record -- goes to the latest introduction.

### Search the registers by phone number (13 Oct 2026)

At the PI's request, the search boxes on the Main-400 Register, Reserve Activation, Organisations and the KII Register
also find records by phone or WhatsApp number (`api/phone_search.PhoneSearchFilter`): Main-400 cases and
organisations by their respondents' numbers, KII records by their own (including additional numbers). Numbers on file
are written every way, often several to a field ("(+263) 242 70396175 or 0242 703 961", "0242 703961-5; ..."), so a
term made only of digits and phone punctuation, with at least six digits once the 263 country code or trunk 0 is
dropped, is matched against the digits of each number: "0772 123 456", "+263772123456" and "772123456" all find the
same record. Other terms search exactly as before, and a Contact RA still finds only their own cases.

### No WhatsApp on a template Meta hasn't approved (13 Oct 2026)

At 08:00 on 13 Oct the automatic reminder run sent 148 WhatsApp reminders to Main-400 cases while all six templates
were still pending at Meta: 120 came back undelivered with Twilio error 63016 (template not approved) and 25 with
63024. Nobody received an unwanted message, and the failed reminders went back to Follow-ups as designed, but the run
used 148 of the day's 250 WhatsApp messages and would have repeated every morning. It went unnoticed because "set up"
meant "a template SID is configured": nothing asked Meta's decision, and Twilio accepts a message on a pending
template and fails it only later, in a delivery report.

- **Reminders:** `twilio_client.whatsapp_reminder_template()` returns nothing while the template is pending or
  rejected, so the reminder goes by SMS if that is set up, or waits on Follow-ups -- not recorded as a failure.
- **Introductions:** `outreach.intro_channel()` uses the SMS with the tap-to-reply WhatsApp link until the
  introduction template is approved; the introduction reminder uses the introduction template while its own waits.
- **Everywhere else:** `outbound.send()` refuses a WhatsApp template Meta has not approved
  (`whatsapp_template_not_approved`), so a single invitation sent from a case or KII record says so at once instead
  of looking sent. A free-text reply inside a conversation the person started needs no template and still goes.
- Meta's decision comes from `twilio_client.template_approvals()` (cached ten minutes); when Twilio cannot be asked
  ("unknown") nothing is blocked. Tests never reach Twilio: `tests/conftest.py` answers "no template known".

### Batch KII invitations (13 Oct 2026)

At the PI's request, the KII Register has **Send KII invitations**, the counterpart of the Main-400 batch
(`apps/kii/batch.py`; `GET/POST /api/v1/kii-invitations/batch/`, PI and Field Coordinator, Supervisor read-only):

- **Who:** KII records never invited (PROSPECT) with a contact for a chosen channel and no open link, from the groups
  ticked (Core-60, Reserve-30, Additional organisations; a hand-made record with no `metadata.pool` counts as
  additional), Core-60 first then KII ID order. *Named informants only* leaves out "(contact not yet identified)"
  records, which otherwise go to the organisation asking for the role.
- **How:** each record goes through `issue_kii_invitation()` then `email_kii_invitation()` / `text_kii_invitation()`,
  as the record's own buttons do, in one transaction: if no channel gets through, the link and the move to INVITED
  are undone. A record invited by hand while the batch runs is skipped.
- **Limits:** batches are `InvitationBatch` rows with `mode="KII"` (choices in the new `options` field), so one batch
  runs at a time across Main-400 and KII, and the daily email cap now counts KII invitation emails as well as
  Main-400 ones -- the cap protects the one study mailbox.
- **WhatsApp waits for Meta:** a batch (KII or Main-400, invitations or introductions) refuses WhatsApp while its
  template is pending or rejected at Meta (`twilio_client.template_waiting`). Before this, the Main-400 batch would
  have accepted WhatsApp, Twilio would have queued every message, each would have failed later with error 63016,
  and the batch would have reported them sent.

### KII self-service records itself (13 Oct 2026)

At the PI's request, an informant who uses their own KII link is now recorded end to end without anyone touching the
platform (`kii.services.advance_on_self_service`, audited `kii.status_changed` with `automatic: true`):

- **Status:** issuing the link moves PROSPECT → INVITED; declining online → DECLINED; the KII Guide arriving from
  KoboToolbox (the 15-minute form sync) → COMPLETED.
- **Consent decides:** the latest decision counts, so someone who declined, then consented and completed, is
  COMPLETED. A KII Guide whose informant never gave participation consent is not counted, and is audited as
  `kii.submission_without_consent` (rule 6).
- **Facts check (new `/ki/[token]/verify`):** the informant checks their own locked pre-interview facts after
  consent, as Main-400 respondents do. Low-confidence facts are asked as open questions, their value never shown.
- **Coding:** completes by itself when everything is confirmed. Corrections, open answers and skipped checks wait on
  the KII Register's **Needs reconciling** list (`GET /api/v1/proit/reconciliation-queue/`), and the researcher's last
  reconciled value completes it.

The gap this closed: KII links had no facts step, and coding cannot complete until a locked profile's facts are
verified. So once all 90 KII profiles were locked on 13 Oct, no self-service informant could ever have completed
without a person, and statuses had never followed self-service at all (KII-0002 was invited, consented and submitted
on 1 Oct and stayed PROSPECT).

### Full system check: status catch-up, Twilio throttle, a banned word, a phone layout (13 Oct 2026)

A whole-system pass found the following.

**Production checks, read-only:**
- No 5xx in 25,000 requests since early October; the only API 404s were bots probing `/.env`
  and the like.
- All services up, backups every 4 hours, certificate valid to 10 Dec.
- 948 backend tests and the 63-test browser suite pass.

**Defects fixed:**
- **Verified cases now catch up to their respondent.** Hand-registered organisations invited
  at S00 and later bulk-verified to S03 sat at S03 holding sent, opened and even QA-passed
  links (23 cases on production).
  - They were miscounted.
  - They were offered to batches and introductions again, so a respondent who had already
    completed the questionnaire could have been invited a second time.
  - Marking a case S03 now walks it along the respondent path to what its links show
    (`sampling.services.catch_up_respondent_path`, audited as `sampling.status_caught_up`).
  - Verification itself is still never inferred: a case invited at S00 stays at S00 until a
    researcher verifies it.
  - `contactable_cases()` also never offers a respondent who has submitted.
  - `manage.py catch_up_case_status [--apply]` repaired the existing cases.
- **Twilio's delivery reports and incoming messages** shared the respondents' 30/minute per-IP
  allowance, so one WhatsApp batch's reports (up to four per message, from a few Twilio
  addresses) would mostly have been refused, and Twilio does not resend them. They now have
  their own scope (`TWILIO_WEBHOOK_THROTTLE_RATE`, 1200/minute), still signature-checked.
- **The respondent's "verify this study" panel** said the research was "formally approved"
  (rule 2). It now says "formal research clearance".
- **The KII record page scrolled sideways on a phone:** the pre-interview profile's field
  picker sized itself to its longest option.
- **Celery's start-up warning:** `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP` is set
  explicitly.

**Browser tests that had gone stale since 6–12 Oct:** the replace-invitation question, the
Communications screen in each role's navigation, and the PI's 21 screens.

### Automatic Reserve replacement, and Reserves that can be contacted (12 Oct 2026)

At the PI's request a Main case that does not take part can be replaced automatically
(`apps/sampling/replacement.py`). While the PI has it switched on (Reserve Activation →
Automatic replacement), the 08:00 run does the following for each Main case whose outcome
the PI ticked:

- **Outcomes and reasons:** Refused (Refusal), Nonresponse exhausted, no reply to the "ask
  first" introduction (the case moves S03/S04 → S13 first, a new transition), Ineligible,
  or Duplicate/inactive (recorded as Inactive).
- **Activation:** the run activates that case's own paired, still-locked Reserve and gives it
  the same Contact RA.
- **Contact:** it introduces the Reserve on WhatsApp; a YES sends its link.
- **Rule 4 still holds.** Every activation goes through `activate_reserve()` with its
  authorised reason, an evidence note saying what happened, and the PI who switched it on
  named as authoriser. That is the standing authorisation. The audit entry is marked
  `automatic`.
- **Limits:** a daily limit (default 20) stops a backlog activating at once.
- **The replaced Main** keeps its outcome, so refusal and nonresponse rates stay right, and
  its open link is revoked.
- **A Reserve that can't be introduced** (templates pending, no mobile) is retried each
  morning, or listed as needing contact details.

**Fixed along the way:** an activated Reserve could never be batched or introduced. Reserves
have no workflow status, and every candidate list filtered on S03/S04, so an activated
Reserve could only be invited one at a time from its case page.
`sampling.services.contactable_cases()` is now the single place batches, the WhatsApp queue
and introductions choose from. It covers Main cases at S03/S04, plus activated Reserves not
yet invited and not having said no. Locked Reserves are never included.

### Communications: every message, every channel, one screen (12 Oct 2026)

At the PI's request, `/admin/communications` replaces Conversations
(`apps/messaging/communications.py`). Until now the portal could not show what it had
said to anyone: Twilio messages were recorded without their text, and the 87 invitation
emails left only an audit entry, with replies sitting unread in Gmail. Now:

- **Sent messages keep their text** (`ProviderMessage.body`), with the personal link and
  manual code replaced by "[personal link]" / "[code]", since a link works like a password
  and only its hash is stored (`outbound.redact` / `scrub`). Email goes through
  `outbound.send_email`, which gives each email its own Message-ID, so replies and bounces
  can be matched back to it.
- **Email replies come in** from the study mailbox every few minutes
  (`apps/messaging/mailbox.py`, PI decision). The mailbox is opened read-only (EXAMINE and
  BODY.PEEK, never STORE). Only email from or to an address on a case or KII record, or
  answering a portal email, is copied in. For anything else only the headers are looked at,
  and nothing is kept. Bounces mark the sent email "not delivered"; emails the team wrote in
  Gmail appear as sent items; links quoted in replies are taken out.
- **WhatsApp from a recorded number** now lands on its case or KII record even without an
  "ask first" introduction. Before, it went to unknown numbers.
- **The thread shows what was never followed.** Invitations sent by hand from the study
  phone appear with "no delivery report". The time the link was first opened is kept from
  now on (`first_opened_at`).
- **Writing a message** is refused when it contains a word a respondent must never see
  (rule 2), when the case is a locked Reserve (rule 4), when the participant withdrew, when
  it is WhatsApp free text outside the 24 hours after their own last message, or when the
  number or address is not on the record.
- **Withdrawal** now erases the text both ways.
- **Who sees what:** `CanUseCommunications` (PI, FC, Contact RA, KII RA; Supervisor reads),
  scoped in one place. The KII RA gains the screen for KII records.

### KII and Main-400 research imported from ChatGPT, for review (11 Oct 2026)

Main-400 has the same import (`POST /api/v1/proit/main-import/`, the Main-400 Register's import
panel) from a Main-400 research pack built on the live questionnaire: Section 2 profile
items (P1-P10) map to PROIT fields, and Sections 3-10 (the measured scales and the
respondent's own views) are marked "Do not answer". Contacts become suggestions on the
case, facts become PROIT proposals; there is no interview-prep sheet, and a locked Reserve
is never researched. One importer serves both (`apps/proit/research_import.py`).

The PI researches KII organisations in ChatGPT with a "KII research pack" workbook (the
organisations, the KII Guide marked question by question, the 32 PROIT catalogue fields
and their codes) and brings back its three filled sheets. `POST /api/v1/proit/kii-import/`
(PI and FC; the KII Register's import panel) loads them into the review flows that already
exist: Fill A becomes contact suggestions on the record's contact-finder panel, Fill B
becomes PROIT `AIProposal`s to Accept / Edit / Reject, and Fill C goes into the KII gap-engine
notes, marked as imported (`apps/proit/kii_import.py`). Nothing reaches a record or a
pre-profile field until a person accepts it. Only catalogue fields are taken, a fact
without a source link is refused, a locked profile is never changed, importing the same
file twice adds nothing, and a preview runs the same code inside a rolled-back transaction.
The pack tells ChatGPT never to answer the KII Guide's own questions: those are the
informant's evidence.

### Ask first, then invite (7 Oct 2026)

At the PI's request the portal can send an organisation a short introduction to the study
asking whether it will take part, before any link (`apps/messaging/outreach.py`). Replies
arrive on the study's Twilio WhatsApp number (`POST /api/v1/twilio/inbound/`, refused
without a valid signature, Twilio's retries ignored by message SID). A **YES** issues the
invitation and sends its approved text, with link and code, back in the chat: WhatsApp
allows free text for 24 hours after the person's own message, and they asked for it, which
is what WhatsApp's opt-in rule wants. A **NO** moves the case to **S12 Refused** (PI decision;
`WORKFLOW_TRANSITIONS` now allows S03/S04 → S12, which before had no status for a refusal
ahead of an invitation) and revokes any open invitation. A yes or a no wrapped only in greetings and
courtesies ("Good day YES", "No thank you" -- `OUTREACH_REPLY_COURTESY_WORDS`) counts as that answer. A business
WhatsApp's automatic greeting (`OUTREACH_AUTO_REPLY_PATTERNS`, since 20 Oct) is shown but does not wait, and the reminder
still goes. Anything else, "no
problem", a question, or yes and no together included, waits (an automatic answer is off since 14 Oct) on the
**Conversations** screen (now Communications), where RAs reply, since the Twilio number is on no phone. No
reply: one reminder after 3 days, then the case is listed on Follow-ups to phone. An
undelivered WhatsApp introduction is re-sent once by SMS with a tap-to-reply WhatsApp link
(Twilio can't receive SMS in Zimbabwe). Numbers are kept as a keyed hash on the outreach
record; what people wrote is erased on withdrawal.

### SMS and WhatsApp through Twilio (7 Oct 2026)

At the PI's request the portal can send invitations and the Day 2 / Day 7 reminders itself,
by SMS and WhatsApp through Twilio (`apps/messaging/twilio_client.py`, `outbound.py`). One
invitation per case, sent on every chosen channel, with Twilio's delivery reports shown on
the invitation history (`POST /api/v1/twilio/status/`, refused without a valid
`X-Twilio-Signature`). Batches (PI and FC) gain SMS and WhatsApp next to email; Contact RAs
send one case at a time for their own cases. The morning reminder run sends due reminders
by WhatsApp when its template is set up, otherwise SMS, to mobiles only; a reminder Twilio
refuses or cannot deliver goes back to Follow-ups and is never re-sent automatically, and
does not count toward Nonresponse.

The reminder code had been written in 2026-09 against the Meta Cloud API, for which no
account was ever provisioned, so no reminder had ever been sent automatically; that client
(`whatsapp_client.py`) and its settings are removed.

What Zimbabwe allows, checked with Twilio on 2026-10-07: an SMS sender must be a registered
name or an international number; two-way SMS is not supported; about US$0.32 per segment
(an invitation SMS is 2 to 3). WhatsApp needs Meta business verification, a number used only
by the API, and Meta-approved templates, and WhatsApp's policy requires opt-in before a
business-initiated message. Those, the data transfer to Twilio and the SMS opt-out wording
are the PI's decisions before switching on.

### Meta busy for a moment no longer fails a search (6 Oct 2026)

During a spell of overload on Meta's side, 11 of 25 contact searches in one batch failed
within minutes ("The AI service is busy right now", "internal server error"): the first
such answer ended the whole search. `apps/proit/muse.py` `post_responses` now waits and asks
again on 429/529, 5xx or a connection failure (`AI_TRANSIENT_RETRY_DELAYS`, default 30, 90
and 180 seconds), keeping the turns the search has already made. A refusal about the request
or the account (400, 401, 402, 403) still fails at once, and a read timeout is not retried
because Meta may already have done and billed that work. `check_ai_provider` never waits.

### One invitation, every channel (6 Oct 2026)

Reported by the PI: an organisation with both a WhatsApp number and an email could only be
sent one. The cause was the screens, not the rules. The link is shown once, and the send
panel put each channel's button behind its own tab; the WhatsApp queue returned only the
WhatsApp text. To email an organisation already sent a WhatsApp invitation, the team issued
a second invitation, which (correctly) made the first link stop working: **49 organisations
on production hold a WhatsApp invitation whose link now says "expired"** (their emailed link
works). At the PI's request those links were switched back on the same day with
`manage.py reopen_superseded_invitations --apply`: a replaced link still in its own dates is
reopened when the case's newer invitation is still waiting, so both messages work; nothing
reopens behind a revoked newer invitation or once the questionnaire has begun, and each
reopened link has an `invitation.reopened` audit entry. Separately, the email endpoint refused any invitation past SENT, so a respondent
tapping the WhatsApp link first blocked the email.

Now the panel shows every channel's button at once and says to use them all; the queue has
**Email the same link**; the email endpoints (Main-400 and KII) accept any link that still
works; and replacing a working invitation asks first. The case-page button also stays
disabled until the invitation history has loaded: the E2E test showed a quick click
replaced a working link before the page knew it existed.

### Follow-ups: dead links and landlines (6 Oct 2026)

Found by a gap audit of the live system, neither reported by anyone.

1. **Reminders for links that no longer worked.** Invitation tokens are only marked EXPIRED
   when someone tries one, so an unopened link past its 14-day date still read SENT, and the
   reminder queue (`apps/messaging/services.py`) kept offering a Day 7 reminder pointing at
   it. A case whose invitation had been revoked, with none issued since, dropped off every
   list while still reading S05 (one such case on production). Reminders now skip any link
   past its date, and Follow-ups lists **Invitations that have run out**
   (`expired_invitations()`) for a new invitation from the case page. 152 open invitations
   were due to expire on 17 and 19 October.
2. **WhatsApp and SMS links to landlines.** `whatsapp_digits()` fell back to any number of
   nine digits or more, so a respondent with only a landline (17 on production) got a wa.me
   link that could never be delivered. It now returns only a mobile (or a number in another
   country's international format), tries both the WhatsApp and phone fields, and the
   invitation panel and Follow-ups say "landline: phone them instead".

### Seventh pass — AI-assisted document coding, human-reviewed (17 Sep 2026)

The PI asked to have AI read an uploaded document, fill the Document Analysis Tool and
submit it, with a second button next to Code this document to choose that option. Built,
with one boundary held regardless of the request: Sections B–L of this form ARE the
study's documentary-analysis method (evidence-strength ratings, hypothesis-support
codes), so nothing generates and files them as a completed research record without a
person checking it first — see `apps/evidence/ai_coding.py`'s docstring for the full
reasoning. Section A's factual metadata (title, author, date, source) is filled from the
document record itself, not the AI, either way.

1. **Auto-fill** (`/admin/documents/[id]/ai-draft`) has Claude read the uploaded source
   file and draft a full answer set (`apps/evidence/ai_coding.py`), grounded with
   page/paragraph locators. A Documentary RA reviews every field in the portal, edits
   what needs it, then clicks **Submit to KoboToolbox**, which posts the reviewed
   answers via KoboToolbox's OpenRosa submission API (`apps/evidence/kobo_submit.py`) —
   the one place in this feature that writes to Kobo, and only on that explicit click.
2. **A real platform quirk, found through live testing before this shipped.** The
   documented OpenRosa submission pattern (`POST {kc-host}/{username}/submission` with a
   root XML element named for the XLSForm's `id_string`) 404s against this deployment.
   Redeploying the asset didn't fix it. The actual requirement, found by testing
   variations against the live project: the root element's `id` must be the **asset
   UID**, not the form's `id_string` — this deployment's OpenRosa backend routes by
   asset UID. Verified with two real test submissions under DOC-ID `TEST-DELETE-ME-0001`
   (confirmed via the data API, then deleted; 0 submissions before and after), then
   pinned in `test_root_element_id_is_the_asset_uid_not_the_form_id_string`.
3. **A second bug, caught in manual UI testing before anyone else saw it:** a document
   that has never had a draft generated has `ai_draft = {}` (the model default) — but an
   empty *object* is truthy in JavaScript, so the review screen showed a brand-new
   document as if it already had a complete AI draft. `DocumentRecordSerializer` now
   serializes an empty draft as `null`.
4. `document_tool_schema.json` (110 fields, checked in) is generated from the deployed
   XLSForm by `manage.py build_document_tool_schema`, then cross-checked against the
   live asset's own parsed field list (`$xpath`) with zero mismatches — the same schema
   drives the AI prompt, the Claude tool-use JSON schema (so a model can't return a
   choice code that doesn't exist on the live form) and the submission XML builder, so
   the three can't quietly drift apart.

**First real run, 19 Sep 2026 — three things a mocked test could not see:**

5. **The AI request was rejected outright.** Claude's tool schema only allows letters, digits,
   `_`, `.` and `-` in a field name, and the form paths contain `/` (`section_a/DOC_ID`).
   Fields are now sent as `section_a__DOC_ID` and mapped back; the corrected schema was
   checked against the real API before release, and `test_tool_schema_property_names_are_valid`
   enforces the same rule.
6. **The AI can read at most 100 pages of a PDF at a time**, and the real NDS2 file is 648.
   A long PDF now asks for a page range (one chapter or evidence unit), sends only those
   pages and tells the model to cite the original page numbers. A range that is missing,
   out of bounds or over 100 pages is refused instantly, before any AI call.
   **Quick add** (2026-09-20): *Documents → New document → Upload and auto-fill* creates the
   record from the file alone (`POST /documents/quick-create/`). In the background the worker
   first reads the document's first pages and fills in the record's title, author, date,
   type, scope, value chain and source (`extract_document_details`; only what the document
   states, blanks stay blank, and a title/type the person typed is kept), then drafts the
   coding form. A file that cannot be used (unsupported, or a long PDF with no pages chosen)
   leaves no record and no file behind. Record details are editable on the record page and
   the draft always shows and submits the record's *current* details
   (`with_current_record_details`). On an existing record, the *Start Auto-fill as soon as
   the file is uploaded* tick box does the same. The authenticity decision and Include/Exclude
   stay human; authenticity and QA status can only change through their own endpoints.
   **Copy for another chapter** (2026-09-20): on a record with a file, `POST /documents/{id}/copy/`
   {title?, pages?} makes another record for a different part of the same source: same author,
   date, source, type and scope, and its **own copy of the file** (removing one never affects
   the other), with authenticity, QA status and draft left empty so every chapter is judged
   on its own. With AI on it starts Auto-fill on those pages (the AI names the part when no
   title is typed). A title or pages is required, and a bad range creates nothing.
   **Read the whole document in parts** (added 2026-09-20): for a longer text, tick the
   option on the review screen. The pages (all of them, or a range of up to 1,500) are cut
   into even parts of about 80 pages, three parts are coded at a time, and one more pass
   combines the part drafts into a single coding (`generate_chunked_draft` in
   `apps/evidence/ai_coding.py`). The combining pass may only use what the parts say, keeps
   the original page locators, judges ratings across the whole document, and unions the
   metrics. Any failing part fails the whole draft rather than skipping pages. The screen
   shows progress ("Read part 4 of 12"), the draft records `_parts` and the total tokens,
   and the review screen warns that ratings need extra care. The Celery worker is single, so
   a long read delays the 15-minute Kobo sync until it ends.
7. **Reading takes minutes; nginx closes a request at 60 seconds.** Generating now runs in
   the Celery worker (`apps/evidence/tasks.py`) and the screen polls
   `ai_draft_status` (running / failed with the reason). A crashed job is recorded as failed
   rather than left "running", a stuck one stops blocking after 12 minutes, and an answer
   cut off by the length limit is never saved as a draft with fields missing.
   Uploads also show a live progress bar: the server saves a file in about a tenth of a
   second, so a slow upload is the connection, and a silent "Uploading…" looked frozen.

### Sixth pass — the KII Guide's own prefilled link (17 Sep 2026)
the wrong reason, that is called out — those were the most dangerous cases, because the
green tick was the reason nobody looked.

### Sixth pass — the KII Guide's own prefilled link (17 Sep 2026)

The PI asked whether the same "code this record" idea applied to Key Informant
Interviews too. It didn't yet, and building it turned up a real query-count regression
before it ever reached a test run.

1. **Continue this interview.** The KII record page now builds a KoboToolbox web-form
   link (`KOBO_KII_FORM_URL`) prefilled with the record's KII-ID
   (`apps/kii/services.py build_kii_coding_url`) -- but deliberately narrower than the
   document version: a KIIRecord identifies a real person, so `participant_name`,
   `participant_role` and organisation never go into the URL, only the system-generated
   ID and the interviewer's own username. The link is withheld -- not merely hidden,
   refused server-side too -- until participation consent is GIVEN; there is no
   legitimate reason to hand out a link to run the interview instrument on someone
   before they have consented to take part.
2. **Caught before merging: the KII register's fixed N+1 query bug, reintroduced.**
   The new `coding_url` field calls the consent check for every row, and
   `has_given_consent()` always issues a fresh query rather than using the
   already-`select_related` consent FK -- exactly the one-query-per-row growth
   `test_kii_register_queries_do_not_grow_with_rows` was written to catch (README
   "Per-row queries", fourth pass). The serializer now only computes `coding_url` /
   `kii_form_configured` for a single-record fetch, never inside the list serializer
   (`isinstance(self.parent, serializers.ListSerializer)`) -- the register itself never
   pays for a field it doesn't use.

### Fifth pass — document analysis on the platform (16 Sep 2026)

The PI asked how document analysis is done on the platform rather than by hand, against
the uploaded documents. It wasn't yet: a Documentary RA registered a `DocumentRecord` in
the portal and separately, by hand, retyped its DOC-ID and details into the KoboToolbox
Document Analysis Tool — a typo there meant the completed coding form could never be
matched back to the right record — and there was nowhere to keep the source file itself.

1. **Code this document.** The document page now builds a KoboToolbox web-form link
   (`KOBO_DOCUMENTS_FORM_URL`) prefilled with the record's DOC-ID, title, author and
   source, the same `?d[...]` mechanism the main questionnaire uses
   (`apps/evidence/services.py build_document_coding_url`). Nothing is retyped, and the
   completed form is guaranteed to land on the right record.
2. **Source file upload.** The document page stores the scan, screenshot or recording
   itself under `PRIVATE_DATA_ROOT` (`DOCUMENT_MAX_UPLOAD_MB`, default 60 MB; a fixed
   extension allow-list), downloadable only by roles with document access, replacing any
   earlier file for that record; every upload and download is audited
   (`apps/evidence/views.py DocumentFileView`).
3. **The frontend proxy corrupted binary request bodies the same way it once corrupted
   binary responses** (see the fourth-pass fix below) — it read the request as text and
   always sent `Content-Type: application/json` upstream, so a multipart file upload
   would have been mangled and rejected by Django. It now forwards the request body as
   bytes and the browser's own `Content-Type` (`frontend/app/api/proxy/[...path]/route.ts`).

### Fourth pass — every screen, every role; performance; PI data access (15 Sep 2026)

1. **Two panels refused the roles viewing them.** The PROIT panel and the reserve-pairing
   list loaded data a KII RA or Contact RA may not see, so the case page showed errors.
   Both now load only for roles that hold the grant.
2. **Two wide menus pushed pages sideways on phones** (register and Form PDFs).
3. **The PI could not get the answers out.** Every portal export held metadata only. The
   PI now downloads each form's full data as an analysis-ready workbook and all
   completed forms as PDFs.
4. **The frontend proxy corrupted every binary download.** It read responses as text,
   re-encoding PDF and Excel bytes. It now streams the body unchanged, and the E2E test
   checks the bytes.
5. **Per-row queries.**
   - Main-400 register: 40 → 2 queries per page.
   - KII register and both CSV exports: one consent query per row removed.
   - Follow-ups: several queries per invited case → a fixed handful.
   - Invitation checks no longer load every invitation.
   - New indexes on the audit log, consent history and submissions.
6. **The go-live preflight crashed once every Main case had been verified to S03.** It
   now picks a clean case at S00–S03 and runs only the remaining steps.
7. **Imported contacts were unusable for WhatsApp.**
   - The importer stored the register's whole "Existing Contact" cell (numbers, emails,
     notes) as the person's name.
   - It left invisible zero-width characters in numbers.
   - The WhatsApp link joined every digit of a multi-number field into one number that
     opened no chat.
   - Fix: `apps/contacts/contact_text.py` splits the cell into name, phone list, first
     reachable mobile and email. It is used by the importer, the WhatsApp links and the
     one-off `manage.py clean_imported_contacts`, which backs up the original values
     first.

### Third pass — go-live audit (14 Sep 2026)

1. **Research answers were publicly downloadable.** Full Kobo payloads sat under nginx's
   `/media/`. Now stored in `PRIVATE_DATA_ROOT` (`/media/` → 404) and included in backups.
2. **Anyone with the public form link could submit for a guessed case.** Portal links now
   carry an HMAC signature; unsigned login-free submissions are set aside and audited.
3. **Nonresponse was set by the calendar while every reminder silently failed**, making a
   case replaceable by its reserve without anyone contacting the respondent. S13 now
   needs every reminder delivered, and Follow-ups sends them by hand.
4. **Staff could not record a phone number** (51 of 400 Main cases had one). Added the
   respondents and contact details panel.
5. **Withdrawal could not be recorded.** Added one audited action.
6. **A reissued invitation left the old link working** once the respondent had consented.
7. **Case status never moved past S05.** It now follows the respondent to S10, and
   coordinators can verify in bulk.
8. **Kobo:**
   - an edit would have duplicated the submission (keyed on `_uuid`);
   - submission times were two hours off;
   - duration was never recorded, so the duration QA rules could not fire.

### Second pass — role, register and respondent-flow audit (Sep 2026)

1. **The eligibility gate was documented but never enforced.**
   `build_redirect_url()` stated in its own docstring that it issues no questionnaire URL
   "without a passed eligibility check and GIVEN participation consent", and
   `docs/28_DEFINITION_OF_DONE.md` says an ineligible respondent is *never* routed to the
   questionnaire. Only consent was checked. Since `/api/v1/consent/` is `AllowAny` with a
   valid token as its only credential, anyone the eligibility screen turned away could
   POST consent directly and be handed a Kobo URL. The test that appeared to cover this
   passed only because it never gave consent — its own comment admitted as much. Fixed in
   `build_redirect_url()` via `contacts.services.has_passed_eligibility`.
2. **`IsQAOrAdmin` was shared across three unrelated modules**, so a KII RA could edit
   documentary evidence and a Documentary RA could take QUAN QA decisions. Split into
   `IsQAOrAdmin` / `CanManageKII` / `CanManageDocuments`.
3. **The KII/document dashboard excluded the very RAs it is for** — it used
   `IsAnalystOrAdmin`, refusing the KII and Documentary RAs that
   `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` grants it to.
   Now `CanViewKIIDocumentDashboard`.
4. **`/api/v1/dashboards/qa/` had no page at all** — the endpoint had existed since
   Phase 6, but nothing consumed it and the nav offered no link to it, so the QA
   dashboard `docs/16_DASHBOARDS_AND_REPORTING.md` specifies simply did not exist in the
   UI. Built as `/admin/dashboard/qa`.
5. **Every role saw all 14 nav links and landed on `/admin/dashboard`**, which four of
   the eight roles are refused. Replaced by `backend/api/navigation.py` as the single
   source of truth, served via `GET /api/v1/auth/me/`.
6. **Registers were unusable at real volumes** — 20 rows per page, no paging control, no
   search, against 400 Main + 400 Reserve + 90 KII + 100 documents. Also, `KIIRecord` and
   `DocumentRecord` had no `Meta.ordering`, so page boundaries were arbitrary and a row
   could appear on two pages or none.
7. **Sign-in shared the generic 30/min anon throttle** with the public respondent
   endpoints. A team behind one office NAT is one IP, so staff logins competed with
   respondent traffic — and DRF's 429 reached the login screen as "Invalid username or
   password". Own scope, and the login route now distinguishes throttling from bad
   credentials.
8. **Every respondent-flow step failed silently** — `try/finally` with no `catch`, so a
   failed request left the button re-enabled and the page unchanged. Worst on consent,
   where the respondent could not tell whether their decision had been recorded.
9. **Appointments could be requested in the past**, landing in the RA's queue already
   missed. Guarded in the picker, re-checked in the page, enforced server-side.
10. **Appointment requests are now consent-gated** (PI decision) — see the respondent
    flow above.
11. **`matched_case` was a bare FK with no validation**, so the API would accept a Main
    paired to another Main, a case paired to itself, or the same Reserve claimed by two
    different Main cases — the last silently breaking the reserve lock. Now routed
    through `sampling.services.set_matched_case` with an audit entry, and exposed as a
    picker on the case detail page instead of requiring Django admin.
12. **A DRF `ValidationError` returned "An error occurred."** with the real text buried in
    `field_errors`, which the respondent flow has no UI for. The envelope now surfaces the
    first field error as the message.

### First pass — end-to-end QA hardening (Sep 2026)

Every respondent-flow and admin screen exercised by hand in a real browser, every
endpoint cross-checked against its documented contract.

1. **Production routing bug (the highest-impact fix)**: Nginx's `location /api/` caught
   *everything* under `/api/`, including the frontend's own `/api/auth/*` and
   `/api/proxy/*` routes (Django only ever mounts `/api/v1/`, `/api/schema/`,
   `/api/docs/`). Confirmed live via `journalctl` that a real visitor had been getting a
   404 on every login and every dashboard fetch for hours. Fixed by routing only
   Django's actual prefixes to the backend and letting the frontend's routes fall
   through to the existing catch-all `location /`.
2. **Audit trail always said "system"**: `AuditContextMiddleware` read `request.user`
   before DRF's JWT authentication had run, so every `AuditEvent` in the system's history
   was attributed to no one. Fixed by reading it lazily, once authentication has
   actually populated it.
3. **`PATCH /api/v1/sample-cases/{id}/` could bypass the S00–S16 state machine
   entirely** — jumping a case straight to `Completed` with no validation and no audit
   trail. Fixed by making the state-machine-controlled fields read-only and adding a
   dedicated, validated transition endpoint.
4. **Appointments had no way to be confirmed/completed/cancelled** by an RA — `status`
   was correctly read-only against public tampering, but that also blocked legitimate
   internal updates. Added a dedicated status endpoint.
5. **The admin "log a contact attempt" form always failed** with a 400 — the serializer
   required a field (`sample_case`) that the view resolves from the URL and was never
   meant to be supplied by the caller.
6. **KII consent gave no visual feedback** — recorded consent decisions existed on the
   model but weren't exposed by the API, so the admin screen couldn't show whether
   participation/recording consent had already been captured.
7. **Kobo pagination** — `fetch_submissions()` only ever read the first page of Kobo's
   paginated data endpoint.
8. **Kobo outages crashed instead of degrading gracefully** — an unreachable Kobo API
   propagated as a raw 500 instead of a clean, informative error.

## Repository layout

```
Digital_Respondent_Portal/
├── AGENTS.md
├── README.md
├── docs/
│   ├── manuals/  # Word manuals: system manual, 8 role guides, respondent guide (+ PDFs)
│   └── tools/    # build_manuals.js + manuals/ (Word manuals), build_guide.py (older PDF guide)
├── deploy/       # deploy.sh, backup.sh, rollback.sh, setup-server.sh, configure-{kobo,email,offsite-backup}.sh
├── nginx/        # research.agribizframework.conf (source of truth, mirrored on the VPS)
├── systemd/      # backend, frontend, celery worker/beat, backup timer, offsite backup units
├── frontend/     # Next.js + TypeScript
└── backend/      # Django + Django REST Framework
```

Same two-folder (`frontend/`, `backend/`) shape as the sibling ABI project — see
`docs/03_SYSTEM_ARCHITECTURE.md` § Repository layout and `docs/20_EMBEDDING_WITH_ABI.md`
for how the two projects share infrastructure without sharing a codebase.

## Documentation

- `AGENTS.md` — ground rules for anyone (human or agent) modifying this codebase; the
  Main-400/Reserve-400 sample, workflow statuses, identifier scheme and QA thresholds
  are fixed research-operations logic and must never be silently changed.
- `docs/INDEX.md` — full documentation index and reading order.
- `docs/06_API_ARCHITECTURE.md` — full endpoint reference.
- `docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md` — Master_ID/Sample_ID generation and the
  full S00–S16 state machine.
- `docs/11_KOBOTOOLBOX_INTEGRATION.md` — Kobo integration design, including the
  reconciliation-vs-webhook decision and this pass's pagination/resilience fixes.
- `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` — consent model, audit requirements,
  de-identified vs. operational export schema.
- `docs/27_AGENT_EXECUTION_PLAN.md` — phased, checkable build task list.
- `docs/28_DEFINITION_OF_DONE.md` — acceptance criteria and go-live checklist.
- `docs/29_RESPONDENT_GUIDE_AND_MESSAGING.md` — the plain-language respondent journey,
  ready-to-use WhatsApp/email/manual-code invitation message templates, and an RA
  troubleshooting table — practical companion to the "Send Invitation" panel.
- `docs/30_PROIT_MODULE.md` — the pre-interview profiling tool: field modules, the
  source-authority hierarchy, the three-value architecture, and the record of the PI's
  risk-acceptance decision to enable it for respondents.
- `docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md` — the approved QA thresholds and
  Participant Information Sheet (now v1.5).
- `docs/33_GO_LIVE_READINESS.md` — what was verified on production, what was fixed,
  and what is left before the first live invitation.
- `backend/api/navigation.py` — not documentation as such, but the single source of truth
  for which role sees which screens. Change it there and nowhere else;
  `backend/tests/test_role_navigation.py` and `frontend/e2e/role-scoped-navigation.spec.ts`
  will tell you if the API permissions disagree.

### User manuals (Word and PDF)

`docs/manuals/` holds the complete documentation set for the people who use the portal.
Every document has a table of contents:

| File | For |
|---|---|
| `ABF-FST_Portal_System_Manual` | Everyone: how the system works end to end, every screen, KoboToolbox, data, security, administration and troubleshooting |
| `ABF-FST_Screen_and_Button_Reference` | Everyone: every screen and every button, with what it does, when to use it, why it exists and what happens next. Generated from `docs/tools/manuals/reference_a.js` and `reference_b.js`; each Role Guide ends with the same material cut down to that role (`reference.js`). When a screen or button changes, change its row there |
| `Role_Guide_1_PI_Admin` | Principal Investigator / System Admin |
| `Role_Guide_2_Field_Coordinator` | Field / Digital Coordinator |
| `Role_Guide_3_Contact_RA` | Contact Research Assistant |
| `Role_Guide_4_QUAN_QA_RA` | Questionnaire (QUAN/Kobo) QA Research Assistant |
| `Role_Guide_5_KII_RA` | Key Informant Interview Research Assistant |
| `Role_Guide_6_Documentary_RA` | Documentary Evidence Research Assistant |
| `Role_Guide_7_Analyst` | Data Analyst |
| `Role_Guide_8_Supervisor` | Supervisor (read-only) |
| `Respondent_Guide` | Survey respondents |
| `RA_Training_Programme_and_Facilitator_Guide` | PI and Field Coordinator running the three-day RA training (schedule, session plans, role-plays, assessment with answer key, register) |
| `RA_Training_Manual` | Research Assistants in training and in the field (study, ethics, data protection, role modules, scripts, scenarios, exercises, checklists, confidentiality declaration) |

Each exists as `.docx` (editable) and `.pdf`. The content lives in
`docs/tools/manuals/*.js` (`tasks.js` holds the step-by-step procedures shared by the
manual and the role guides). Edit it there, not in the Word files. The screenshots in
`docs/manuals/screens/` were taken from a separate database of **fictional
demonstration data**, never the live registers.

Rebuild the manuals on Windows with Microsoft Word installed. Word fills in the
tables of contents and page numbers, then exports the PDFs:

```bash
cd docs/tools && npm install && node build_manuals.js
```

```bash
powershell -ExecutionPolicy Bypass -File docs/tools/finalise_manuals.ps1
```

### The earlier end-user guide (superseded by the manuals above)

`docs/tools/build_guide.py` builds a complete, non-technical **user guide PDF** for the
research team — sign-in, what each role sees, every screen, inviting a respondent, the
respondent's experience, a full walkthrough and troubleshooting. The script is the
tracked source of truth; the PDF it writes alongside itself is gitignored.

```bash
backend/.venv/Scripts/python.exe docs/tools/build_guide.py   # Windows
backend/venv/bin/python docs/tools/build_guide.py            # Linux/macOS
```

Bump `REVISION` in that script whenever the content changes, so a printed or emailed copy
can be told apart from an earlier one.

## Domain

Live at `research.agribizframework.com` (shares the ABI project's production host and
TLS setup, deployed with its own Nginx server block, database, and systemd services —
see `docs/20_EMBEDDING_WITH_ABI.md`).

The real Main-400/Reserve-400, KII and documentary-evidence registers **are** loaded and
all 400 Main cases are verified to S03, but no live invitation has been issued yet — the
first one is the PI's call per `docs/28_DEFINITION_OF_DONE.md` and
`docs/33_GO_LIVE_READINESS.md`. Treat the production database as
holding real, identifying research data: it is not a scratch environment.
