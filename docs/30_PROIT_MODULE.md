# 30 — PROIT (Pre-Interview Respondent & Organisation Intelligence and Verification Tool)

Full specification: `ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx`, provided by the PI on
2026-09-12. This document is a condensed engineering reference to that spec, not a
replacement for it — the docx is the source of truth for anything not covered here.

## What it is

A pre-interview desk-research layer. Before a respondent is contacted, a researcher
looks up publicly available background facts about the organisation/respondent from
approved sources (a strict 4-tier hierarchy: statutory registers > official/annual
reports > reputable media/bios > corroborated social content), records provenance
(source, date, locator, confidence) for each fact, and a human reviews and locks a
"pre-profile" before the respondent is ever contacted. The respondent then confirms,
corrects, or declines each pre-filled fact instead of answering from zero — that
substitution is the actual burden-reduction mechanism. It never pre-fills, skips, or
infers any frozen ABI/NFM/Digital-Readiness/Institutional-Environment/FST scale item —
only non-core descriptive background fields.

## Governance status — read before enabling anything respondent-facing

The document's own status line: **"DEPLOYMENT-READY CONTROLLED ADD-ON — subject to
supervisor/ethics change-control decision."** Its recommended deployment sequence puts
an **"Ethics/change-control review"** step before any soft launch or real respondent
use. `settings.PROIT_ENABLED_FOR_RESPONDENTS` (env var
`PROIT_ENABLED_FOR_RESPONDENTS`, default `False`) is the actual enforcement of that gate
in code: researchers can build and lock pre-profiles against real or synthetic cases
regardless, but `/i/<token>/verify` and the respondent-profile API always behave as if
no pre-profile exists — the respondent flow is unchanged — until this is explicitly
turned on, which should only happen after that ethics/change-control approval.

## Implementation (`backend/apps/proit/`)

- **Models**: `PreProfile` (one per `SampleCase` or `KIIRecord`, exactly one of the
  two — same pattern as `consent.ConsentRecord`/`contacts.Appointment`),
  `PreProfileField` (the three-value architecture: `preliminary_documentary_value`,
  `respondent_value`, `reconciled_value`, kept permanently independent),
  `EvidenceSource` (provenance, one-to-many per field). `PROIT_FIELD_CATALOG` in
  `models.py` is the field-ID whitelist transcribed from the document's Section 6
  modules A–F — the mechanism that makes "never pre-fill a frozen core item" a closed
  set enforced in code, not a convention.
- **Services** (`services.py`) enforce the document's own "non-negotiable deployment
  rules": no documentary value may be locked without at least one evidence source;
  a pre-profile can only be locked by a recorded reviewer; once locked, fields/evidence
  become immutable; a respondent's correction (`record_verification`) can only happen
  after lock and never touches `preliminary_documentary_value`; confidence
  (HIGH/MODERATE/LOW) and gap classification (VERIFY_ONLY/VERIFY_AND_PROBE/ASK_FULL/
  SKIP_BACKGROUND_ONLY) are computed from the evidence itself, not asserted by a
  researcher. `PROBE_TEMPLATES` + `render_probe_template()` implement Section 10's KII
  probe-template library as simple, auditable string substitution — not an automated
  NLP pipeline, which the document doesn't specify and which would risk fabricating
  probe content.
- **API** (`views.py`/`urls.py`, under `/api/v1/proit/`): researcher-side CRUD gated by
  `IsFieldCoordinatorOrAdmin` (`field-catalog/`, `probe-templates/`, `pre-profiles/`,
  `pre-profiles/<id>/fields/`, `fields/<id>/evidence/`, `pre-profiles/<id>/lock/`);
  respondent-side (`respondent-profile/`, `respondent-verify/`) token-authenticated
  like the rest of the respondent-facing API, `AllowAny` + `validate_token()`, and
  gated by `PROIT_ENABLED_FOR_RESPONDENTS`. The respondent-facing serializer
  (`RespondentPreProfileFieldSerializer`) never exposes `sources`/provenance —
  the document's own Developer Implementation Contract: "never expose source-internal
  notes to respondents."
- **Admin UI**: a "Pre-Interview Profile (PROIT)" panel
  (`frontend/components/admin/PreProfilePanel.tsx`) on both the sample case detail page
  and the KII detail page — create a profile, add cataloged fields with a documentary
  value, attach evidence sources, and lock.
- **Respondent UI**: `frontend/app/i/[token]/verify/page.tsx`, inserted into the flow
  between consent and the completion-mode choice. Self-skips straight to `/choice`
  whenever there's nothing to verify (PROIT disabled, no pre-profile, or not locked) —
  the respondent never sees a blank or broken screen either way.

## What's intentionally not built yet

- No UI control for `source_authority` (Tier 1–4) on the evidence-add form — settable
  via the API/Django admin if a researcher wants a source explicitly marked Tier 1
  (which affects the HIGH-confidence computation). A small follow-up, not a gap in the
  underlying rule.
- Section 13's "Researcher Pre-Profile Screen" (a single consolidated review card
  before interview) and Section 9's five-panel KII gap-engine UI (KNOWN/VERIFY/
  UNKNOWN/CONTRADICTION/PROBE) are represented by the `PreProfile` model's own
  Module I fields (`known_evidence_summary`, `unresolved_gaps`, `contradictions`,
  `priority_probe_questions`) but have no dedicated panel yet — a researcher fills them
  in via `PATCH /api/v1/proit/pre-profiles/<id>/`.
- Burden-reduction metrics (Section 11) are computed and stored
  (`background_questions_avoided`, `burden_reduction_score`) but not yet surfaced on
  any dashboard.

## Tests

`backend/tests/test_proit.py` — the field-ID whitelist rejecting a non-cataloged ID,
lock requiring provenance on every documentary value, lock being irreversible/
immutable through the service layer, confidence/gap-classification derivation, a
respondent correction never overwriting the documentary value, the burden-reduction
formula, permission checks (Contact RA cannot manage pre-profiles), and the
`PROIT_ENABLED_FOR_RESPONDENTS` gate (both the disabled-returns-null path and the
enabled path only exposing displayable fields with no source data).
