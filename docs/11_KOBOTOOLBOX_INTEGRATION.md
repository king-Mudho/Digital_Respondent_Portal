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
