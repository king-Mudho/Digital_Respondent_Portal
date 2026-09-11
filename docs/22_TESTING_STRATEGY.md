# 22 — Testing strategy

## Backend — pytest + pytest-django

- **Reserve lock (highest priority)**: unit test that `sampling.services.is_invitable()`
  returns `False` for every `RESERVE`/`LOCKED` case and that every invitation-issuing
  endpoint calls through it — a regression here breaks the study's core integrity
  guarantee.
- **Identifier generation**: test Master_ID/Sample_ID format and uniqueness under
  concurrent import (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`).
- **Token lifecycle**: generation entropy/format, hashing (raw token never persisted),
  expiry, single-valid-token supersession, revocation, rate limiting
  (`10_INVITATION_AND_CONSENT.md`).
- **Eligibility & consent gating**: no Kobo redirect URL is issued without a passed
  eligibility check and a `GIVEN` participation consent; KII recording consent is never
  inferred from participation consent.
- **Workflow status engine**: invalid S00–S16 transitions are rejected
  (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`).
- **Reconciliation**: given a mocked Kobo API response including an *edited* submission
  (changed `last_edited_at`, same `kobo_submission_uuid`), confirm the reconciliation job
  updates the existing `QUANSubmission` rather than creating a duplicate or missing it —
  this is the test that directly proves the webhook-edit-blindspot design decision in
  `11_KOBOTOOLBOX_INTEGRATION.md` actually works.
- **QA engine**: each threshold in `15_QA_AND_DATA_QUALITY.md` has a hard-stop and a
  soft-flag test case; confirm a hard stop never auto-resolves without a human
  `QAEvent`.
- **Privacy**: explicitly assert every dashboard/aggregate endpoint response never
  contains `Organisation.name`, `Respondent.full_name`, or unbanded amounts
  (`18_DATA_PRIVACY_AND_COMPLIANCE.md`).
- **API tests**: every endpoint in `06_API_ARCHITECTURE.md` — auth enforcement on
  internal endpoints, correct 4xx on an invalid/expired/revoked token.

## Frontend — component tests

- Consent/eligibility step components block progression without the required action.
- Token-in-URL handling degrades correctly (clear error state) for an invalid, expired
  or revoked token — never a generic crash.

## End-to-end — Playwright

- **Happy path**: invitation validation → organisation confirmation → eligibility →
  consent → participation choice → Kobo redirect (mocked Kobo form in test env) →
  reconciliation picks up a synthetic submission → QA queue shows it → QA decision →
  `QA_PASSED`.
- **Reserve-lock scenario**: attempt to issue an invitation against a locked Reserve
  case via the API and confirm it is rejected before any UI path is even exercised.
- **Ineligible-respondent scenario**: eligibility gate fails → referral path shown,
  questionnaire never reachable.
- **Consistency check**: assert the workflow status shown on the internal case-detail
  screen exactly matches `SampleCase.workflow_status` from the API — the frontend must
  never diverge from or infer the backend value.
- **Dashboard**: internal-role login → every dashboard renders without exposing any
  individual organisation/respondent name.

## Non-functional checks

- Completion-time instrumentation on the respondent flow (consent-to-Kobo-redirect
  duration) — a sanity signal, not a CI gate.
- Lighthouse or equivalent audit on the respondent-facing screens for mobile
  performance and accessibility (`19_LANGUAGE_AND_ACCESSIBILITY.md`).

## CI expectation

All backend and frontend automated tests must pass before a phase in
`27_AGENT_EXECUTION_PLAN.md` is marked complete for that layer — see
`23_DEPLOYMENT_ARCHITECTURE.md` for the CI pipeline this runs in.
