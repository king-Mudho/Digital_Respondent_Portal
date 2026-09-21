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
regardless of this flag, but `/i/<token>/verify` and the respondent-profile API always
behave as if no pre-profile exists — the respondent flow is unchanged — until it is
turned on.

**Turned on in production (2026-09-12).** No PROIT-specific ethics/change-control
review was obtained — the two documents offered as possible sign-off (CUT's general
Research Ethics Clearance, dated 24 August 2026, and a PhD supervision confirmation
letter from Dr L. Chikazhe, dated 20 August 2026) both predate this document's own
12 September 2026 spec date, so neither could have reviewed PROIT's specific mechanism
(pre-interview background research on a named organisation/respondent, shown back to
them for verification before the interview). This was flagged directly to the PI,
including why this gate is more specific than the POTRAZ data-protection question
resolved earlier (see `18_DATA_PRIVACY_AND_COMPLIANCE.md`) — POTRAZ was a legal
registration-threshold question a general ethics review plausibly already covered;
PROIT's own document names a new consent/privacy-relevant mechanism as its own
change-control trigger. The PI's decision, given directly: proceed without a separate
PROIT-specific review, as the PI's own documented risk acceptance, not an ethics-body
determination. `PROIT_ENABLED_FOR_RESPONDENTS=True` is set in production's environment
only (`config.settings.base`'s own default stays `False`, so any new/staging
environment still starts with the respondent-facing side off until deliberately
configured).

**2026-09-15: PI confirms PROIT is covered.** The PI stated in writing that he holds the
permissions and rights, under his CUT student research clearance, to run PROIT as part of
the study, and approved it. Recorded here as the PI's confirmation of coverage; no
PROIT-specific review document is held in this repository.

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
  value, attach evidence sources (with a source-authority tier picker feeding directly
  into the HIGH-confidence computation), and lock. KII pre-profiles additionally get a
  "KII adaptive gap engine" section (Section 9): free-text KNOWN/UNKNOWN/CONTRADICTION/
  PROBE notes, a role-specific-module picker, and a probe-template helper that renders
  one of the document's 7 stakeholder-role templates (Section 10) with the researcher's
  own evidence substituted in.
- **Respondent UI**: `frontend/app/i/[token]/verify/page.tsx`, inserted into the flow
  between consent and the completion-mode choice. Self-skips straight to `/choice`
  whenever there's nothing to verify (PROIT disabled, no pre-profile, or not locked) —
  the respondent never sees a blank or broken screen either way.
- **Researcher review screen** (`frontend/app/admin/proit/[id]/page.tsx`, linked from
  the panel as "Researcher review screen"): Section 13's single consolidated
  pre-interview card, composed read-only from the same data — Case, Organisation,
  Evidence (every source across every field, flattened), Bankability context
  (finance/tenure/audited-reports/insurance/offtake/infrastructure only), Gap summary
  (computed unknowns and conflicted fields, the researcher's own notes, and a static
  reminder of the document's sensitive-data exclusions), and Interview plan (fields
  grouped by `gap_classification`, role-specific module, executive-short-form
  indicator, priority probes). Shows a clear "not yet locked" banner before lock, since
  `gap_classification` isn't computed until then.

## Saved to KoboToolbox

When a profile reaches RECONCILED (or a coordinator records a protocol deviation) the portal sends it to the
**ABF-FST PROIT Interview Profile** KoboToolbox form (`KOBO_PROIT_ASSET_UID`), once, in the background
(`apps/proit/kobo_submit.py`, Celery task `push_profile_to_kobo`, retried five times). One record per case:
the header (record ID, QUAN or KII, reconciliation status, counts, gaps, contradictions) and one repeat row per fact
(public value, confidence, gap class, sources, the respondent's status and value, the interviewer comment and the
reconciled value). The form definition is `apps/proit/kobo_form.py`; `deploy/kobo/build_proit_form.py` builds the
XLSForm from it. `manage.py push_proit_to_kobo` re-sends anything that failed. Nothing is sent while
`KOBO_PROIT_ASSET_UID` is blank.

## What's intentionally not built yet

- Burden-reduction metrics (Section 11) are computed and stored
  (`background_questions_avoided`, `burden_reduction_score`) and shown on both the
  panel and the review screen once a profile is locked, but not yet surfaced on any
  dashboard.

## Tests

`backend/tests/test_proit.py` — the field-ID whitelist rejecting a non-cataloged ID,
lock requiring provenance on every documentary value, lock being irreversible/
immutable through the service layer, confidence/gap-classification derivation, a
respondent correction never overwriting the documentary value, the burden-reduction
formula, permission checks (Contact RA cannot manage pre-profiles), and the
`PROIT_ENABLED_FOR_RESPONDENTS` gate (both the disabled-returns-null path and the
enabled path only exposing displayable fields with no source data).
