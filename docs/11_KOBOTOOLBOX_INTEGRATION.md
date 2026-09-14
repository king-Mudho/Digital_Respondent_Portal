# 11 — KoboToolbox integration

KoboToolbox remains the primary quantitative data-capture engine. This portal passes
controlled identifiers and mode information into Kobo, and retrieves submission status
through an approved integration. This document closes the QC review gap: the v1.0
blueprint's Section 6.3 already chose scheduled reconciliation over webhook-only sync,
which is the *correct* call, but never stated why — this document states it explicitly
so a future developer cannot "simplify" to webhook-only and silently lose edited
submissions.

## The webhook constraint (why reconciliation, not webhook-only)

KoboToolbox's REST Services webhook fires **only on new-submission creation**. It does
**not** fire when a submission is later edited (e.g. an RA correcting a field after a
phone-assisted session, or a respondent's Kobo-side edit before final lock). This is
documented Kobo behaviour, not an assumption. A webhook-only integration would therefore
silently miss every post-creation edit, which matters directly to this study's QA
process — edited answers must reach the QA queue.

**Design consequence**: the webhook is used only as a fast "heads-up" signal to trigger
an *early* reconciliation pull for that submission's asset. It is never trusted as the
source of truth and never writes `QUANSubmission` rows directly (`08_BACKEND_
ARCHITECTURE.md`). The scheduled reconciliation pull, run via Celery Beat, is the actual
source of truth and is what a developer must not remove or "optimise away."

## Reconciliation schedule

- **Frequency**: every 15 minutes during active fieldwork hours, every 60 minutes
  overnight (both configurable via environment/Celery Beat schedule, not hardcoded).
- **Mechanism**: full pull of the Kobo asset's submission list via the Kobo API
  (`/api/v2/assets/{asset_uid}/data/`), diffed against `QUANSubmission` by
  `kobo_submission_uuid`; any submission whose Kobo-side last-modified timestamp is
  newer than `QUANSubmission.last_edited_at` is treated as updated and re-queued for QA
  review of the changed fields.
- **Logging**: every run writes a `ReconciliationLog` row (`05_DATABASE_ARCHITECTURE.md`)
  recording new vs. updated counts and any Sample_ID mismatches — a submission with no
  matching hidden-field Sample_ID is flagged for manual RA investigation, never silently
  dropped or silently auto-matched.

## Hidden or controlled fields

Passed into Kobo via the tokenised launch URL (`GET /api/v1/kobo/redirect-url/`, see
`06_API_ARCHITECTURE.md`):

- Master_ID
- Sample_ID
- Invitation_Wave
- Administration_Mode
- Respondent_Role_Category
- Consent_Status / Consent_Version reference
- RA_ID (for assisted administration)
- Start/submit timestamps (Kobo's own metadata, reconciled in, not portal-supplied)
- Portal_Token_ID (a non-identifying token reference — the `InvitationToken.id`, never
  the raw token or its hash)

## Administration-mode coding

| Code | Mode |
|---|---|
| 01 | WEB_SELF — direct web self-administration |
| 02 | WHATSAPP_LINK_SELF — self-completion after WhatsApp invitation |
| 03 | PHONE_ASSISTED — telephone interviewer-administered |
| 04 | WHATSAPP_CALL_ASSISTED — interviewer-assisted via WhatsApp Call |
| 05 | VIDEO_CALL_ASSISTED — Teams/Zoom/Meet or equivalent |
| 06 | FACE_TO_FACE — targeted contingency administration |

## Integration contract (developer handover requirement)

Before Phase 1 build starts, freeze and record: the exact Kobo asset UID(s) used for
production vs. the staging test form (see `23_DEPLOYMENT_ARCHITECTURE.md`), the exact
hidden-field names as they appear in the live Kobo form (must match this document's
field list exactly, case-sensitive), the Kobo API token's scope and storage location
(environment secret, never in frontend code — `AGENTS.md`), and the REST Services
webhook shared-secret. This is listed as an explicit Phase 0 pre-development artefact in
`27_AGENT_EXECUTION_PLAN.md`.

## Test asset requirement

A dedicated Kobo **test/staging form**, structurally identical to the production form,
is required so `22_TESTING_STRATEGY.md`'s E2E reconciliation test and the original
blueprint's Section 22 "test with synthetic/test cases only" step can run without ever
touching the live Main-400 Kobo asset.

## Implementation status (Sep 2026 hardening pass)

- **Pagination**: `apps.kobo.client.KoboClient.fetch_submissions()` follows the v2 data
  endpoint's `next` link until Kobo reports none left. An earlier version only fetched
  the first page — harmless while the fieldwork dataset is small, but would have
  silently dropped every submission beyond page 1 once a survey grew past Kobo's default
  page size. Covered by `backend/tests/test_kobo.py`.
- **Graceful failure**: if the Kobo API call itself fails (unreachable, invalid token,
  invalid/empty asset UID, timeout, 5xx), `reconcile()` now records a `ReconciliationLog`
  row with `error_message` set instead of letting the exception propagate out of the
  Celery Beat task or the manual-trigger endpoint. `POST /api/v1/kobo/reconcile/` returns
  a clean `502` with that message rather than a raw `500`.
- **Manual sync**: `GET /api/v1/kobo/reconciliation-status/` (most recent run) and the
  existing `POST /api/v1/kobo/reconcile/` back a "KoboToolbox sync" panel on the admin QA
  queue page (`/admin/qa`) — a "Sync now" button plus last-run status, so an RA/PI/admin
  doesn't have to wait for the next scheduled Celery Beat tick to pull fresh submissions.
- **Not connected is a state, not a failure (2026-09-14)**. Three settings, configured
  from two different places in KoboToolbox:
  - `KOBO_FORM_URL` — the deployed form's public web link, copied from the project's
    *Collect data* page (e.g. `https://ee.kobotoolbox.org/x/AbCd1234`). The respondent's
    questionnaire link is this URL plus `?d[<field>]=<value>` prefill parameters
    (KoboToolbox's documented syntax), values percent-encoded. It is **not** derivable
    from the asset UID: web forms are served by the Enketo host (`ee.`) under their own
    short form ID. Until this date the link was built as `kf.kobotoolbox.org/x/<asset_uid>`,
    which would have 404'd for every respondent even with a correct asset UID.
  - `KOBO_ASSET_UID` + `KOBO_API_TOKEN` — needed only for reconciliation (the API on `kf.`).
  With `KOBO_FORM_URL` blank, `GET /kobo/redirect-url/` returns `503
  questionnaire_unavailable` (after the consent and eligibility gates, which are refused
  on their own terms first) and the respondent is offered the assisted phone/WhatsApp
  route instead of a dead link. With the asset UID or token blank, the scheduled task
  skips without writing a `ReconciliationLog` row, `POST /kobo/reconcile/` returns `503
  kobo_not_configured`, and the QA sync panel says "not connected yet" with Sync now
  disabled. Before this, production wrote 125 error rows in a day against
  `/api/v2/assets//data/`; those rows were left in place.
- **Still open (needs the PI / a Kobo account owner, not engineering)**: all three
  settings are empty in production. Hidden fields must sit at the top level of the
  XLSForm (not inside a group — a grouped field needs its group path in the `d[...]`
  name), and their exact names still need freezing against the real live form per
  "Integration contract" above before Phase 11 go-live.

## Main-study XLSForms (r2, 2026-09-14)

Kobo-ready copies of the three frozen instruments, prepared from the PI's files in
`D:\Mr Saina\Final Interview Forms from September to November\Kobo-ready 2026-09-14\`
(originals untouched; every change is listed in each workbook's README sheet; no
measurement, interview or coding item wording changed). All three pass ODK Validate.

| Form | form_id | Who fills it | Portal link |
|---|---|---|---|
| Main Study Questionnaire v3.0 | `abf_fst_main_study_questionnaire_v3` | Respondent (web) or RA (Collect) | `KOBO_FORM_URL`, `KOBO_ASSET_UID` |
| KII Guide v3.0 | `abf_fst_main_study_kii_v3` | Interviewer | `KII_ID` must be the register's `KII-NNNN` |
| Document/Platform/Media Analysis Tool v2.0 | `abf_fst_main_study_doc_analysis_v2` | Coder | `DOC_ID` must be the register's `DOC-NNNN` |

Only the Questionnaire is reconciled by the portal. Its integration contract:

- Nine **top-level** `hidden` fields with exactly the names `build_redirect_url()` sends
  (`master_id … ra_id`), checked name-for-name against the code.
- `SAMPLE_ID`, `ORG_CODE` and `ADMIN_MODE` are asked only when `sample_id` / `administration_mode`
  arrived blank, i.e. the form was opened without the portal link. The original required
  `SAMPLE_ID` on the first screen blocked every web respondent.
- Top-level calculates `SAMPLE_ID_FINAL` and `ADMIN_MODE_FINAL` hold the portal value when
  present, otherwise the entered one. `reconcile()` uses `sample_id`, falling back to
  `SAMPLE_ID_FINAL`, and maps `ADMIN_MODE_FINAL` to a mode code when `administration_mode` is
  blank (`web_portal` 01, `telephone` 03, `whatsapp_assisted` 04, `face_to_face` 06).

### Production connection (2026-09-14)

KoboToolbox side, done through the API: the Questionnaire project
(`aefzZwVQV927tqtTgsP9oz`, web form `https://ee.kobotoolbox.org/x/fSOJejrV`) runs the r2
form, and AnonymousUser now has `add_submissions` on it. The account has "require
authentication" on, so without that grant every respondent following the portal link
would have met a KoboToolbox login page. KII (`an49gwkpkGfYjS6B4NDNqh`) and Documents
(`a3vpgw6T4FbZGjQqmUgBND`) remain staff-only. The token was checked read-only with
`KoboClient.fetch_submissions()` (0 submissions).

Server side: `sudo bash deploy/configure-kobo.sh` after deploying — writes the KOBO_*
settings, blanks them for staging, restarts, runs one sync, and prints the webhook secret
for the REST Service (send `_uuid` only).

Completed 2026-09-14 15:5x: `configure-kobo.sh` run on production (link and sync configured,
manual sync ok with 0 submissions, webhook 202 with the secret); REST Service
`he5Nst8pNqjhjZAu493j5x` registered on the Questionnaire (JSON, `_uuid` only,
`X-Kobo-Shared-Secret` header). A questionnaire link built in a rolled-back transaction
has all nine prefill fields and opens on Enketo (HTTP 200). No test submission was made
against production data. The API token used was shared in chat; rotate it, then re-run
`configure-kobo.sh` and update the REST Service header if the secret changes (it is kept
on re-run).
