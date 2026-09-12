# 27 — Agent execution plan

Execute phases in order, and **only after the PI has approved this documentation set in
writing** (`AGENTS.md` ground rule 1). Check off each task in place (`- [ ]` → `- [x]`)
as you complete it. Do not mark a task done until it actually works (migrations run,
tests pass, screen renders). Commit at the end of each phase: `phase(N): <summary>`.

## Open questions

*(Agent: add any ambiguity you hit here, with the assumption you made, instead of
guessing silently — see `AGENTS.md` § Open questions convention. The items below are
already known open questions carried from this documentation set's own gap-closing
work — resolve them with the PI before or during the phase noted, not silently.)*

- **PI sign-off (2026-09-11).** The PI approved this full documentation set
  (`docs/00`–`28`) and this execution plan in writing via chat, unblocking `AGENTS.md`
  ground rule 1. For the Phase 0 items that are compliance/content decisions rather than
  engineering (QA rule thresholds, UI palette, Shona/Ndebele PIS translation stance,
  WhatsApp template wording), the PI directed: proceed using this documentation set's
  own proposed provisional defaults, and keep them flagged here for real confirmation
  later — same convention as the sibling ABI project. Meta template approval remains
  genuinely open and blocks Phase 11 go-live only, not early development
  (`docs/28_DEFINITION_OF_DONE.md`).
- **Phase 2 — actor_family/value_chain/size_class/entity_type category lists.
  RESOLVED (2026-09-12).** Neither `docs/05_DATABASE_ARCHITECTURE.md` nor the original
  blueprint enumerated these (only "CharField (choices)"), so a provisional placeholder
  set was implemented in `backend/apps/sampling/models.py` so migrations/tests/UI had
  something concrete. Replaced against the actual approved sampling register
  (`ABI_ABF-FST_QUAN_Latest_Register_2026-09-09.xlsx`) ahead of the real Main-400/
  Reserve-400 import: the register's own "Stratum Allocation" sheet revealed the real
  design stratifies by Province x Actor Family x Size Class only, not x Value Chain as
  this codebase had assumed, and gave the real category sets for Actor Family (8 values)
  and Size Class (5 values). Value Chain and Entity Type became free text (the real
  register's data for both is far richer than any small fixed list). See
  `backend/apps/sampling/models.py`'s module/class docstrings for the corrected schema.
- **Phase 3 — Kobo hidden-field names and edit-detection mechanism.** Implemented
  against a documented, reasonable assumption (see Phase 3 note above and
  `backend/apps/kobo/services.py` module docstring) since the real Kobo form/asset
  doesn't exist yet. Must be verified/adjusted once a real Kobo asset is provisioned.
- **Phase 5 — draft Participant Information Sheet text.** No approved PIS/consent
  wording exists yet (Phase 0 item, still open). Wrote a plain-English draft
  (`frontend/lib/constants/participantInformation.ts`, version `v1.0`) so the consent
  module has real content to render and test against. Must be replaced with the PI/
  ethics-office-approved text before go-live; bump the version string when it changes.
- **Phase 7 — ConsentRecord.sample_case made nullable, kii_record added.** `docs/05`
  models `ConsentRecord.sample_case` as required, but KII participants drawn from
  stakeholder categories often have no Main-400 `SampleCase`. Closed by making the FK
  nullable and adding an alternative `kii_record` FK (exactly one of the two required at
  the model level). Flagging per `AGENTS.md`'s doc-schema-gap convention, same as the
  actor_family/value_chain placeholder in Phase 2.
- **Kobo production asset UID and WhatsApp Business Platform account.** Not yet
  provisioned — these require the PI/sponsor to create real external accounts
  (KoboToolbox, Meta Business). Development proceeds against the documented API
  contracts (`docs/11`, `docs/12`) with env-var placeholders; dev/staging must point at a
  dedicated Kobo test asset once one exists, never a production asset.

- **Phase 0 — POTRAZ / Data Protection Officer determination. RESOLVED (2026-09-12).**
  `18_DATA_PRIVACY_AND_COMPLIANCE.md` specified the compliance question; the PI's
  determination is that Chinhoyi University of Technology's Research Ethics Clearance
  (Annex 19, Form GRSD 17 SEBS/06/2025, approved 24.08.2026) and the study's operation
  under the University's institutional research governance covers this position — see
  `18_DATA_PRIVACY_AND_COMPLIANCE.md` for the full record. No longer blocks Phase 11.
- **Phase 0 — QA rule threshold values.** `15_QA_AND_DATA_QUALITY.md` proposes concrete
  engineering defaults (e.g. 5–90 minute plausible duration window) precisely so the PI
  has specific numbers to confirm or adjust rather than an abstract placeholder. Treat
  these as provisional until the PI signs off.
- **Phase 0 — visual palette.** `21_UI_UX_GUIDELINES.md` proposes a blue/neutral
  academic palette distinct from ABI's green/gold, pending sponsor/PI confirmation.
- **Phase 0 — Shona/Ndebele Participant Information Sheet.** `19_LANGUAGE_AND_
  ACCESSIBILITY.md` flags this as a low-cost mitigation worth considering even within
  the English-only v1.0 interface decision — PI to confirm whether to produce translated
  PIS documents ahead of Phase 1.
- **Phase 0 — developer/team assignment.** Not a specification question but a staffing
  one: who builds this, given the September 2026 Phase 1 target has little runway left
  by the time this plan is approved.

---

## Phase 0 — Governance, specification & environment provisioning

- [x] PI reviews and approves this full documentation set (`docs/00`–`28`) in writing.
      *(2026-09-11, via chat — see "Open questions" above.)*
- [x] Resolve the POTRAZ/Data Protection Officer position
      (`18_DATA_PRIVACY_AND_COMPLIANCE.md`). *(2026-09-12: covered by CUT's Research
      Ethics Clearance and the study's institutional research governance — see
      `18_DATA_PRIVACY_AND_COMPLIANCE.md` for the full record.)*
- [x] Confirm QA rule threshold defaults with the PI (`15_QA_AND_DATA_QUALITY.md`).
      *(2026-09-11: proceed with the documented proposed defaults, flagged provisional.)*
- [x] Freeze the identifier-scheme spec (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`) —
      already specified in this doc set; PI confirmed no change needed (2026-09-11).
- [ ] Freeze the Kobo integration contract: asset UIDs (production + test), hidden-field
      names, API token scope, webhook shared secret (`11_KOBOTOOLBOX_INTEGRATION.md`).
      *(Blocked on a real KoboToolbox account being provisioned by the PI/sponsor.)*
- [x] Provision hosting (same VPS as ABI or a second small VPS — decide and record).
      *(2026-09-11: same VPS as ABI, `66.29.139.201` — cost containment, per
      `20_EMBEDDING_WITH_ABI.md`.)*
- [ ] Provision a separate PostgreSQL database (`drp_db`) and Redis instance.
      *(Phase 10 of this plan.)*
- [ ] Provision WhatsApp Business Platform account; submit utility-category templates
      for Meta approval (`12_CONTACT_CRM_AND_MESSAGING.md`) — start immediately, 3–5
      business day lead time. *(Blocked on the PI/sponsor creating the Meta Business
      account; not something engineering can provision.)*
- [x] Provision the DNS subdomain `research.agribizframework.com` and confirm the
      no-cross-link decision with whoever owns the ABI production site
      (`20_EMBEDDING_WITH_ABI.md`). *(Done in Phase 10: `A research ->
      66.29.139.201` added by the user via Namecheap, confirmed propagated; no
      navigational cross-link exists in either app's UI, confirmed by inspection of
      both codebases.)*
- [ ] Confirm approved consent text / Participant Information Sheet is final and ready
      to paste into the consent module. *(Using this doc set's draft disclaimer text
      (`18_DATA_PRIVACY_AND_COMPLIANCE.md`) as a placeholder pending the PI's final PIS.)*
- [x] Assign the developer/team for this build. *(This agent, 2026-09-11.)*
- [x] Confirm developer/frontend package manager choice (pnpm or npm) matching ABI's.
      *(npm — matches the ABI project's `frontend/package-lock.json`.)*

## Phase 1 — Repository scaffold

- [x] Create the two-folder repo layout (`frontend/`, `backend/`, `docs/`, `AGENTS.md`,
      root `README.md`) exactly as in `03_SYSTEM_ARCHITECTURE.md`.
- [x] Scaffold `backend/` as a Django project with the `config/` and `apps/` structure
      from `08_BACKEND_ARCHITECTURE.md`; create all thirteen empty apps (`accounts,
      sampling, contacts, consent, invitations, kobo, messaging, kii, evidence, qa,
      dashboards, costs, audit`). `accounts.User`/`Role` implemented now (pulled forward
      from Phase 2) since a custom `AUTH_USER_MODEL` must exist for Django to boot at
      all; the rest of Phase 2's models follow as specified.
- [x] Scaffold `frontend/` as a Next.js + TypeScript project with the structure from
      `07_FRONTEND_ARCHITECTURE.md`.
- [x] Add `.env.example` files (backend and frontend) exactly per
      `24_ENVIRONMENT_CONFIGURATION.md`.
- [x] Set up `requirements/base.txt`, `dev.txt`, `prod.txt` and `frontend/package.json`
      with pinned versions from `04_TECH_STACK.md`.
- [x] Set up Celery + Celery Beat scaffold (`config/celery.py`), no tasks yet.
- [ ] Set up the CI pipeline (lint, type-check, test stubs) per
      `23_DEPLOYMENT_ARCHITECTURE.md`. *(Deferred to Phase 9 alongside the full test
      suite, so the CI config lints/tests something real rather than an empty stub.)*
- [x] Confirm `python manage.py runserver` and `npm run dev` both boot cleanly with
      placeholder pages. *(Verified 2026-09-11: `manage.py check`/`migrate` clean
      against a local `drp_dev` Postgres 18 database; `npm run dev` serves the neutral
      landing page at `http://localhost:3000`, screenshot-verified in-browser; `tsc
      --noEmit` clean.)*

## Phase 2 — Core backend models & identifier/sampling control

- [x] Implement `accounts`, `sampling`, `contacts`, `consent`, `invitations` apps' models
      per `05_DATABASE_ARCHITECTURE.md`. `kii.KIIRecord` also pulled forward from Phase 7
      (full field set, per docs) since `contacts.Appointment.kii_record` FKs to it.
      **Resolved (2026-09-12)**: `actor_family`/`value_chain`/`size_class`/`entity_type`
      choice lists were not enumerated anywhere in `docs/05` or the original blueprint
      (only "CharField (choices)") — implemented with a placeholder provisional set (see
      docstring in `apps/sampling/models.py`) for engineering purposes, then replaced
      against the actual approved sampling register ahead of the real Main-400/
      Reserve-400 import (see "Open questions" above and Phase 10's import notes below).
      Province (10 Zimbabwe provinces + 2-letter codes) was always objective fact, not a
      placeholder.
- [x] Implement `sampling.services.is_invitable()` and the reserve-lock enforcement path
      (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`, `AGENTS.md` ground rule 4). Also wired
      into `invitations.services.issue_invitation()` (raises `TokenNotInvitable`).
- [x] Implement Master_ID/Sample_ID generation exactly per
      `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` (DB-sequence + `select_for_update`,
      verified race-free under 20 concurrent threads).
- [x] Implement the S00–S16 workflow status state-transition table
      (`apps/sampling/services.py` `WORKFLOW_TRANSITIONS`) — invalid transitions rejected
      and audit-logged.
- [x] Implement invitation token generation/hashing/expiry/revocation
      (`10_INVITATION_AND_CONSENT.md`) — 32-byte CSPRNG + 8-char manual code, both salted
      SHA-256, single-valid-token supersession, revocation.
- [x] Run and commit initial migrations.
- [x] Write the reserve-lock and token-lifecycle unit tests from
      `22_TESTING_STRATEGY.md` — these must pass before continuing. *(24/24 passing,
      2026-09-11: reserve lock, Master_ID/Sample_ID format+uniqueness+concurrency,
      workflow transitions, token lifecycle, consent gating.)*

## Phase 3 — Kobo integration & reconciliation

- [x] Implement the `kobo` app: `QUANSubmission`, `ReconciliationLog`, Kobo API client.
      **Open item**: the exact hidden-field names as echoed back in a real Kobo
      submission payload are not yet frozen (no Kobo account provisioned) — implemented
      assuming the payload echoes the same field names used to populate the launch URL
      (`master_id`, `sample_id`, etc.); see `EXPECTED_HIDDEN_FIELDS` docstring in
      `backend/apps/kobo/services.py`. Must be verified against the real Kobo form once
      it exists.
- [x] Implement the scheduled reconciliation Celery Beat task per
      `11_KOBOTOOLBOX_INTEGRATION.md` — seeded as `django_celery_beat` `PeriodicTask`
      rows (15 min active-hours / 60 min overnight crontabs), DB-config-driven per
      `AGENTS.md` ground rule 7 rather than hardcoded. Active-hours window (06:00-22:00)
      is a placeholder pending PI confirmation of actual fieldwork hours.
- [x] Implement the webhook receiver as a heads-up trigger only, never a direct write.
      Validates `X-Kobo-Shared-Secret` against `KOBO_WEBHOOK_SHARED_SECRET`.
- [x] Write the edited-submission reconciliation test from `22_TESTING_STRATEGY.md`.
      *(Passing: same `kobo_submission_uuid`, changed field, confirms update not
      duplicate, confirms `qa_status` re-enters `PENDING` rather than staying at its
      prior value.)* Edit detection uses a content-hash diff of the full payload each
      pull rather than depending on any specific Kobo metadata field for "last edited"
      — see the design-decision docstring in `kobo/services.py`; robust regardless of
      which Kobo deployment/version is eventually used.
- [x] Confirm the Kobo redirect URL is generated correctly with all hidden fields
      (`06_API_ARCHITECTURE.md`) — gated on `consent.services.has_given_consent()`, the
      single enforcement point (raises `KoboRedirectDenied` otherwise, tested).

## Phase 4 — QA engine

- [x] Implement `qa` app: `QARuleThreshold` (seeded from `15_QA_AND_DATA_QUALITY.md`
      defaults via migration, pending PI confirmation — see Phase 2's flagged
      provisional-defaults item), `QAEvent`. `evidence.DocumentRecord` pulled forward
      from Phase 7 (full field set per docs) since `QAEvent.document_record` FKs to it,
      same reasoning as `kii.KIIRecord` in Phase 2.
- [x] Implement hard-stop vs. soft-flag evaluation logic
      (`apps/qa/services.py evaluate_submission()`), wired into
      `kobo.services.reconcile()` so every new/updated `QUANSubmission` is evaluated
      automatically, per `15_QA_AND_DATA_QUALITY.md` QA decision flow step 1.
      `logic_violation_hard_stop_rules`/`logic_violation_soft_flag_rules` and
      `required_field_names`/`optional_field_names` are seeded empty as extension
      points — genuinely can't be populated for real until a real Kobo form/asset exists
      (same open item as Phase 3's hidden-field-name assumption).
- [x] Implement the QA queue API (`GET /api/v1/qa/queue/`) and human decision-recording
      flow (`POST /api/v1/qa/submission/{id}/decision/`, mandatory note enforced).
      Scoped to `QUANSubmission` for now; KII/documentary-evidence queue items extend
      this in Phase 7 alongside those apps' full workflow wiring.
- [x] Unit test every threshold's hard-stop/soft-flag behaviour. *(12/12 passing:
      duration min/max, missing required field hard-stop, missing-optional-percent,
      duplicate-window, human ACCEPT/REJECT/QUERY flow, note-required validation,
      confirms a hard stop never auto-resolves without a human `QAEvent`.)* Full suite:
      42/42 passing — this pass also caught and fixed a real bug in
      `kobo.services.reconcile()` (an in-memory `QUANSubmission.submitted_at` stayed a
      raw string until DB round-trip, breaking `qa.services`' duplicate-window datetime
      arithmetic; fixed by parsing Kobo timestamps explicitly before `.create()`).

## Phase 5 — Respondent frontend flow

- [x] Build R01–R10 per `07_FRONTEND_ARCHITECTURE.md` and `21_UI_UX_GUIDELINES.md`.
      Also had to build the remaining public API surface first (invitation
      validate/issue/revoke, eligibility, consent-submit, appointment-request views) —
      Phases 2-4 built the models/services for these but only Kobo/QA had views/urls
      wired; 9 new API tests cover the full chain (`tests/test_api_respondent_flow.py`).
- [x] Wire the eligibility referral path — ineligible respondents see a referral message
      in place (no separate route needed; matches the docs/07 route table's "R04 with
      referral path" note) and never reach consent/Kobo (tested both at the API layer
      and via a live browser walkthrough).
- [x] Wire consent capture. **KII-recording-consent flow deferred to Phase 7** alongside
      the rest of the KII module's actual UI (the `consent` app's model/service already
      supports it as a separate `consent_type`, per `AGENTS.md` ground rule 6 — nothing
      to retrofit later, just not wired to a screen yet since KII scheduling doesn't
      have one either).
- [x] Wire the Kobo redirect handoff — gated on `has_given_consent()`, verified live
      (redirect URL only returned after consent; 403 `consent_required` otherwise).
- [x] Confirm no ABI score, band, or financing language appears anywhere in this flow
      (`AGENTS.md` ground rule 2/3, `18_DATA_PRIVACY_AND_COMPLIANCE.md`) — spot-checked
      every screen's copy; the verbatim research disclaimer is sourced from one shared
      constant (`lib/constants/disclaimers.ts`), not duplicated ad hoc, matching ABI's
      own discipline.

**Verified live in-browser** (Next.js + Django dev servers, real DB): full happy path
R02→R08 end to end against the real API; invalid-token error state; ineligible-
respondent referral (never reaches consent/Kobo); 375px mobile viewport, no overflow.
Backend: 51/51 tests passing. Frontend: 7/7 Vitest tests passing (`ApiError` mapping,
invalid-token error state, eligibility gating both directions), `tsc --noEmit` clean.

**Placeholder content flagged for PI/ethics-office confirmation before go-live**: the
Participant Information Sheet text (`frontend/lib/constants/participantInformation.ts`)
is a draft, not the approved PIS — see `docs/27_AGENT_EXECUTION_PLAN.md` "Open
questions".

## Phase 6 — Research Operations Centre frontend

- [x] Build A01–A12 per `07_FRONTEND_ARCHITECTURE.md`. Also built the JWT auth relay
      (`app/api/auth/{login,logout,me}`, `app/api/proxy/[...path]`) per the docs/07
      directory-structure note ("app/api/ -- Next.js route handlers, auth cookie relay
      only"): the JWT lives only in an httpOnly cookie, never in client-readable
      storage; every internal API call goes through the proxy route, which attaches the
      Bearer token server-side and transparently refreshes on a 401. Also built the
      remaining backend API surface these pages needed: `sample-cases`
      list/detail/activate-reserve, `costs`, `kii`/`documents` list-create, `audit` log
      — Phases 2-5 built the underlying models/services but not all the views/urls.
      A07 (KII register) and A08 (documents) are basic list views for now; full
      scheduling/transcript/provenance workflow UI is Phase 7, alongside those apps'
      full build-out. A12 (data-lock export) is Phase 8, per its own DoD dependency on
      the de-identified export existing first.
- [x] Wire the six dashboards (`16_DASHBOARDS_AND_REPORTING.md`), confirming no
      identifying data leaks into any aggregate view — automated test
      (`test_dashboards_and_reserve.py::test_dashboard_never_exposes_identifying_fields`,
      parametrised across all six) asserts the organisation name and `full_name` never
      appear in any dashboard response, not just a visual check.
- [x] Wire the QA queue, reserve-activation flow, and audit log views — reserve
      activation requires selecting one of the five authorised reasons plus a note (no
      free-text "other" escape hatch in the UI, matching the backend's own constraint);
      verified live that activation writes `activated_by`/`activated_at` and an
      `AuditEvent` in one transaction.

**Verified live in-browser** against real dev servers: login (JWT cookie set/read
correctly), executive dashboard (real aggregate counts), Main-400 register + case
detail + contact timeline, QA queue (empty-state correct), audit log (showed every
action from the Phase 5 respondent-flow walkthrough: `invitation.issued`,
`eligibility.checked`, `consent.recorded`, correctly attributed and timestamped).

Backend 62/62, frontend 8/8 tests passing; `tsc --noEmit` clean.

## Phase 7 — Contact/CRM, KII & documentary evidence

- [x] Implement `contacts`/`messaging` reminder queue per
      `12_CONTACT_CRM_AND_MESSAGING.md` (queued, never auto-sent beyond the approved
      sequence). `ReminderSequenceStep` (day_offset, channel, template) is config-driven
      per `AGENTS.md` ground rule 7, seeded with Day 2/Day 7 WhatsApp steps via
      migration. **Design note**: Day 0 "invitation" is the invitation token itself
      (already sent via `invitations.services.issue_invitation`), and Day 4-5 "telephone
      follow-up" is modelled as an RA task (`ContactEvent.next_action_date`), not an
      automatable template send — a phone call can't be "sent" by Celery. Day 7 with no
      contact moves the case to `S13_NONRESPONSE`
      (`messaging.services.exhaust_nonresponse_cases`), tested.
      **Bug found and fixed this phase**: invitation issuance never advanced
      `SampleCase.workflow_status` at all — nothing moved a case off S03/S04, so the
      reminder sequence would have had no cases to act on. Fixed in
      `invitations.services.issue_invitation()`, which now advances S03→S04→S05 on
      first send and never regresses a case already further along (tested).
- [x] Implement WhatsApp Business Platform integration once templates are Meta-approved.
      **Cannot be completed** — no Meta Business account exists (Phase 0 open item, not
      an engineering blocker). Built `messaging.whatsapp_client.WhatsAppClient` against
      the documented Cloud API request shape; it raises `WhatsAppNotConfigured` (fails
      loudly, logged as `MessageStatus.FAILED`) rather than silently pretending to send
      when credentials are absent — verified by test.
- [x] Implement `kii` app and frontend per `13_KII_MODULE.md`. Status flow
      (INVITED→SCHEDULED→COMPLETED/DECLINED/NO_SHOW) and independent transcript/coding
      status progression, both backed by explicit transition tables. Recording consent
      is enforced as a hard gate on `mark_completed(with_recording=True)` — verified by
      test that participation consent alone is never sufficient (AGENTS.md ground rule
      6). Frontend: register + create form + detail page with all four workflow
      controls, verified live against the real API.
- [x] Implement `evidence` app and frontend per `14_DOCUMENTARY_EVIDENCE_MODULE.md`.
      Authenticity assessment (UNVERIFIED→VERIFIED/DISPUTED) always records a reviewer;
      a document cannot reach `qa_status=INCLUDED` while still UNVERIFIED (tested); a
      DISPUTED document is retained, never deleted, with the dispute reason captured in
      `interpretive_memo`. Frontend: register + create form + detail page, verified live.

**Schema gap closed**: `ConsentRecord.sample_case` was required per `docs/05`, but many
KII participants (stakeholder categories like sector experts or financial-institution
reps) have no Main-400 `SampleCase` at all. Made it nullable and added `kii_record` as
the alternative subject, with a model-level check that at least one is set — flagged in
"Open questions" since it's a doc-schema correction, not silently guessed.

Backend 82/82, frontend `tsc --noEmit` clean. Verified live in-browser: KII record
creation, status transition (INVITED→SCHEDULED→COMPLETED), document creation, and the
"cannot include before authenticity assessed" UI hint, all against the real API.

## Phase 8 — Privacy, audit & exports

- [x] Confirm every disclaimer from `18_DATA_PRIVACY_AND_COMPLIANCE.md` appears on every
      required screen. docs/18 requires it on "the consent step, the completion page,
      and any export" (narrower than ABI's list, which also requires a results screen
      and certificate panel this portal doesn't have — no score is ever shown here).
      Verified present, sourced from the one shared `RESEARCH_DISCLAIMER` constant, on
      `/i/[token]/consent`, `/i/[token]/done`, and `/admin/export`.
- [x] Confirm consent capture blocks data persistence until given — structural, not just
      checked: `kobo.services.build_redirect_url()` calls
      `consent.services.has_given_consent()` as its only gate (tested since Phase 3/5).
- [x] Confirm `AuditEvent` entries are created for every action listed in
      `18_DATA_PRIVACY_AND_COMPLIANCE.md` ("invitation issuance/revocation, consent
      change, QA decision, reserve activation, data lock"). **Bug found and fixed**: QA
      decisions were never audit-logged (`qa.services.record_human_decision()` created
      only the `QAEvent`, no `AuditEvent`) — fixed, tested
      (`test_exports.py::test_qa_decision_is_audited`). The other four were already
      covered (Phases 2/6). "Data lock" itself has no dedicated model/endpoint anywhere
      in `docs/05`/`docs/06` — it names the Phase 11 go-live event (freezing further
      collection), which is an operational PI decision at data-lock time, not a Phase 8
      engineering deliverable; nothing to build here yet.
- [x] Implement the de-identified analysis export and the full operational export
      (`06_API_ARCHITECTURE.md`), with an automated test asserting no identifying field
      appears in the de-identified one. `GET /api/v1/export/analysis/`
      (`IsAnalystOrAdmin`) vs. `GET /api/v1/export/operational/` (`IsAdminOnly`) — CSV,
      documented schema difference (contact fields present only in the operational one).
      Frontend: `/admin/export` (A12), verified live end to end including the
      role-permission split (Analyst can reach the de-identified export, not the
      operational one).

Backend 87/87 tests passing.

## Phase 9 — Testing pass

- [x] Run the full backend test suite; all green. *(87/87, plus `ruff check .` clean and
      `manage.py check` clean — ruff added this phase, deferred from Phase 1's CI item.)*
- [x] Run the full frontend component test suite; all green. *(8/8 Vitest, `eslint .`
      clean, `tsc --noEmit` clean.)*
- [x] Run the Playwright E2E suite (happy path, reserve-lock, ineligible-respondent,
      dashboard privacy) from `22_TESTING_STRATEGY.md`; all green. Also added the fifth
      scenario `22_TESTING_STRATEGY.md` lists (the "consistency check": case-detail
      workflow status matches the API exactly). Happy path is scoped to what a browser
      can actually exercise — the reconciliation/QA-queue/QA_PASSED tail has no browser
      UI trigger (no real Kobo submission arrives during a test run) and is already
      covered by `tests/test_kobo.py`/`tests/test_qa.py` on the backend, not duplicated
      here as a fake step. **5/5 passing** against real dev servers.
      Built `apps/sampling/management/commands/seed_drp_dev.py` (idempotent, synthetic
      data only, per `docs/23_DEPLOYMENT_ARCHITECTURE.md`'s "test/synthetic cases only"
      rule) to give the suite deterministic fixtures — this was referenced in the root
      README's quick-start since Phase 1 but never actually built until now.
      **Gap found and fixed this phase**: only 2 of the 6 documented dashboards
      (Executive, Cost) had frontend pages after Phase 6 — Sampling, Contact and KII/
      Document existed as API endpoints only, with no page to visit. Added the three
      missing pages (`/admin/dashboard/sampling`, `/admin/dashboard/contact`,
      `/admin/dashboard/kii-documents`) so the dashboard-privacy E2E scenario could
      actually cover "every dashboard," not just two of six.
      Also set up the CI pipeline (`.github/workflows/ci.yml`, deferred from Phase 1) --
      lint (ruff/eslint) + type-check + pytest + Vitest on every push/PR, Playwright E2E
      on merge to `main` (rename once the actual staging/production branch is decided —
      `docs/23` doesn't name it yet). **Not yet verified against a real GitHub Actions
      run** — this repository has no remote yet (local git only this session); YAML
      syntax validated, and every step mirrors a command already run and passing
      locally.

## Phase 10 — Deployment prep & staging rehearsal

- [x] Write Nginx config and `systemd` units per `23_DEPLOYMENT_ARCHITECTURE.md`.
      Deployed live to the production VPS (shared with ABI, `66.29.139.201`):
      separate Nginx server block (`research.agribizframework.conf`), separate app
      user (`agribiz-drp`) and directory (`/srv/agribiz-drp`), separate loopback
      ports (8100/3100) so the two apps never collide, four systemd units (backend,
      frontend, Celery worker, Celery beat). Redis installed fresh (ABI doesn't use
      it). DNS (`research` → `66.29.139.201`) added by the user via Namecheap and
      confirmed propagated; SSL issued via Certbot and verified live over HTTPS.
      **Resource decision recorded**: confirmed with the user before proceeding that
      deploying on the same ~956MB-RAM VPS as ABI (rather than a second VPS) was
      acceptable, given the explicit "decide at Phase 0" note in `docs/04_TECH_
      STACK.md`; tuned Gunicorn/Celery down accordingly. Observed ~260-360MB
      available under normal load post-deploy — workable but genuinely tight; see
      `docs/DEPLOYMENT.md` "Resource note".
      **Two real bugs found and fixed during this deployment**: (1) `git archive`
      on the Windows workstation converted shell script line endings to CRLF,
      breaking every script's shebang on the Linux target — fixed with a
      `.gitattributes` file forcing `eol=lf`, not by patching the server copy.
      (2) The `agribiz-drp` system user had no home directory (`--no-create-home`),
      which `npm ci` needs for its cache — fixed in `setup-server.sh` and documented
      in `docs/DEPLOYMENT.md` troubleshooting.
- [ ] Stand up the staging environment against the dedicated Kobo test asset.
      **Not done as a separate environment** — no second VPS was provisioned (the
      ~956MB RAM budget doesn't comfortably support a third full stack alongside ABI
      and DRP), and no Kobo test asset exists yet (Phase 0 open item). The rehearsal
      below ran directly against what becomes production instead, with synthetic
      data deleted immediately after — see `docs/DEPLOYMENT.md` "Staging rehearsal".
- [x] Run the backup/restore drill against the RPO/RTO targets. Genuinely verified,
      not just scripted: seeded synthetic data, ran `backup.sh`, restored the backup
      into a scratch database (`drp_restore_test`), confirmed the seeded rows were
      actually present (2 organisations, 2 sample cases, 1 invitation token), then
      dropped the scratch database and deleted the synthetic data from production.
- [ ] Rehearse the full go-live rollout checklist (`23_DEPLOYMENT_ARCHITECTURE.md`) on
      staging with synthetic cases only. **Partially done**: verified live over the
      real HTTPS domain (invitation validation → confirm → eligibility screens,
      admin JWT login), confirmed HTTPS validity (item 1 of the checklist) and the
      backup/restore drill (item 4). Item 3 (POTRAZ position) is resolved — see
      `18_DATA_PRIVACY_AND_COMPLIANCE.md`. Items 2 (full 15-item `docs/28` checklist)
      and 5 (WhatsApp Meta approval) remain open — item 5 is genuinely not
      engineering-completable (external Meta account); item 2 is already covered by
      the Phase 9 automated suite against local dev, not independently re-run
      item-by-item against this exact deployment. Both explicitly Phase 11's gate, not
      Phase 10's.
- [ ] Conduct user acceptance testing with PI, Field Coordinator and one RA. Requires
      the PI/Field Coordinator/RA's own participation — not something to simulate.

Production database confirmed genuinely empty (`Organisation.objects.count() == 0`,
`User.objects.count() == 0`) after the rehearsal, ready for the PI's own first admin
account and, eventually, real Main-400 import — see below for when that happened and
what it does and doesn't mean for Phase 11.

## Post-Phase-10 hardening pass (Sep 2026)

A full end-to-end QA pass -- every respondent-flow (R01-R10) and admin (A01-A12) screen
exercised by hand in a real browser against a freshly seeded local database, then
against production, plus a systematic cross-check of every documented endpoint against
its actual implementation. Full details in `README.md` "Notable fixes" and each fix's
own test file; summarised here for the phase record:

- **Production routing bug, found live**: Nginx's `location /api/` on
  `research.agribizframework.com` caught the frontend's own `/api/auth/*` and
  `/api/proxy/*` routes (Next.js) as well as Django's, since Django only ever mounts
  `/api/v1/`, `/api/schema/`, `/api/docs/`. Confirmed via `journalctl -u drp-backend`
  that a real visitor had been getting a 404 on every login and dashboard fetch for
  several hours. Fixed in `nginx/research.agribizframework.conf`, applied to the live
  server with the user's explicit approval, verified via a temporary admin account
  (created and deleted for the check only) that login -> Executive Dashboard now
  renders correctly end-to-end.
- **Audit trail always attributed actions to no one** (rendered "system" in the UI) --
  `AuditContextMiddleware` read `request.user` before DRF's JWT authentication had run.
  Fixed and confirmed live: a fresh action now correctly shows the signed-in username.
- **`sampling`/`contacts` serializer gaps**: `PATCH /api/v1/sample-cases/{id}/` could
  bypass the S00-S16 state machine entirely (no validation, no audit trail); Appointment
  status had no legitimate update path at all; the admin "log a contact attempt" form
  always 400'd because `ContactEventSerializer.sample_case` was writable-and-required
  when the view supplies it from the URL. All three fixed with dedicated read-only
  fields / endpoints and regression tests.
- **KII consent gave no UI feedback** -- `participation_consent`/`recording_consent`
  existed on the model but weren't exposed by the serializer. Fixed; the
  human-decision-required guard itself (recording completion needs separate recording
  consent) was independently confirmed to already work correctly via a real browser
  click.
- **Kobo integration hardened**: `fetch_submissions()` only read the first page of
  Kobo's paginated v2 data endpoint (silent data loss risk once a survey exceeds one
  page); a Kobo outage crashed the reconciliation task/endpoint instead of degrading
  gracefully. Both fixed, plus a new "KoboToolbox sync" panel on `/admin/qa` (manual
  "Sync now" + last-run status) using a new `/api/v1/kobo/reconciliation-status/`
  endpoint.

Backend: 107/107 tests passing, `ruff check` clean. Frontend: `tsc --noEmit` clean.
All fixes deployed to production via `deploy/deploy.sh` and re-verified live.

## Real sampling/KII/documentary evidence data import (2026-09-12)

The PI provided the three real, approved registers and directed that they be entered
into the live production database as PI/Admin. All three are now imported and verified
live. This is real data entry into the production system, distinct from and ahead of
Phase 11's go-live decision (see note at the end of this section on what it does and
doesn't unblock).

- [x] **QUAN Main-400 + Reserve-400** (`ABI_ABF-FST_QUAN_Latest_Register_2026-09-09.xlsx`)
      — `manage.py import_quan_register`. Surfaced the real stratification-scheme
      mismatch closed under Phase 2/"Open questions" above (Province x Actor Family x
      Size Class, not x Value Chain) before any data was written. Also found and fixed,
      live: `SampleCaseListCreateView.create()` never actually called
      `create_sample_case()` (pre-existing latent bug, unrelated to this import, caught
      by the import's own dry-run); a `StratumDefinition` duplicate-row bug from earlier
      example-data entry; three field-width limits too narrow for real data
      (`StratumDefinition.code`, `Respondent.phone`/`whatsapp_number`,
      `Organisation.district`). Result: 800 organisations, 400 Main + 400 Reserve
      `SampleCase` rows, 100 strata, 128 respondent contacts, all 400 Main<->Reserve
      pairs wired via `matched_case`. Idempotent, dry-run verified against production
      before the real run, counts confirmed live via the API and admin UI.
- [x] **KII Core-60 + Reserve-30** (`ABI_ABF-FST_KII_Latest_Register_2026-09-09.xlsx`) —
      `manage.py import_kii_register`. Found the same category of gap: all 90 real rows
      are genuinely "Not contacted"/"Available", but `KIIStatus` had no status for that.
      Added `KIIStatus.PROSPECT` (identified in the sampling frame, not yet approached)
      and made `preferred_mode` optional. Result: 90 `KIIRecord` rows (60 Core + 30
      Reserve), all `PROSPECT`, 55 with a specifically named contact (either the
      register's own named individual or a research-verified current officeholder), 35
      honestly naming the organisation with "(contact not yet identified)" rather than
      inventing a person.
- [x] **Documentary Evidence register**
      (`ABI_ABF-FST_Documentary_Evidence_Register_v3.0_12Sep2026.xlsx`) —
      `manage.py import_document_register`. Confirmed this register has no separate
      "Reserve" list (a single 100-document sheet across 13 thematic Blocks) before
      importing. Mapped the register's 61 granular "Type" values onto
      `DocumentType`'s OFFICIAL/SECONDARY/PLATFORM split via an explicit, auditable
      table; widened `DocumentRecord.value_chain` for real values that didn't fit.
      Result: 100 `DocumentRecord` rows (82 OFFICIAL, 17 SECONDARY, 1 PLATFORM).

All three imports add a `metadata` JSONField (Organisation/SampleCase, KIIRecord,
DocumentRecord respectively) preserving every register column with no dedicated model
field losslessly — nothing invented, nothing discarded. Each command supports
`--dry-run` and is idempotent (safe to re-run). Full backend suite, ruff, `tsc --noEmit`
and the full Playwright suite stayed green through all three.

**What this does and doesn't mean for Phase 11**: the real sample frame, KII prospect
pool and documentary evidence corpus now exist in production. No real invitation has
been sent to any actual respondent, and no real KII/document work has started — that
remains gated on the PI's own Phase 11 go-live decision below, unchanged.

## Phase 11 — Go-live

- [ ] Verify `28_DEFINITION_OF_DONE.md` in full, including the 15-item go-live checklist.
- [ ] PI sign-off.
- [ ] Issue the first live Main-400 invitations.
