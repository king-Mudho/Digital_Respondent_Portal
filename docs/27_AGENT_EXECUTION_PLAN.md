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
  engineering (POTRAZ/DPO position, QA rule thresholds, UI palette, Shona/Ndebele PIS
  translation stance, WhatsApp template wording), the PI directed: proceed using this
  documentation set's own proposed provisional defaults, and keep them flagged here for
  real confirmation later — same convention as the sibling ABI project. POTRAZ/DPO
  determination and Meta template approval remain genuinely open and block Phase 11
  go-live only, not early development (`docs/28_DEFINITION_OF_DONE.md`).
- **Phase 2 — actor_family/value_chain/size_class/entity_type category lists.**
  Neither `docs/05_DATABASE_ARCHITECTURE.md` nor the original blueprint enumerate these
  (only "CharField (choices)"). Implemented with a provisional placeholder set in
  `backend/apps/sampling/models.py` so migrations/tests/UI have something concrete;
  must be confirmed or replaced against the actual approved sampling register before
  real Main-400 import — this directly affects stratum definitions and is a sampling-
  design decision, not an engineering one.
- **Phase 3 — Kobo hidden-field names and edit-detection mechanism.** Implemented
  against a documented, reasonable assumption (see Phase 3 note above and
  `backend/apps/kobo/services.py` module docstring) since the real Kobo form/asset
  doesn't exist yet. Must be verified/adjusted once a real Kobo asset is provisioned.
- **Phase 5 — draft Participant Information Sheet text.** No approved PIS/consent
  wording exists yet (Phase 0 item, still open). Wrote a plain-English draft
  (`frontend/lib/constants/participantInformation.ts`, version `v1.0`) so the consent
  module has real content to render and test against. Must be replaced with the PI/
  ethics-office-approved text before go-live; bump the version string when it changes.
- **Kobo production asset UID and WhatsApp Business Platform account.** Not yet
  provisioned — these require the PI/sponsor to create real external accounts
  (KoboToolbox, Meta Business). Development proceeds against the documented API
  contracts (`docs/11`, `docs/12`) with env-var placeholders; dev/staging must point at a
  dedicated Kobo test asset once one exists, never a production asset.

- **Phase 0 — POTRAZ / Data Protection Officer determination.**
  `18_DATA_PRIVACY_AND_COMPLIANCE.md` specifies the compliance question but not its
  answer — this requires the PI and CUT's legal/ethics office, not the development
  team. Blocking for go-live, not for early development against synthetic data.
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
- [ ] Resolve the POTRAZ/Data Protection Officer position
      (`18_DATA_PRIVACY_AND_COMPLIANCE.md`). *(Blocks Phase 11 go-live only.)*
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
- [ ] Provision the DNS subdomain `research.agribizframework.com` and confirm the
      no-cross-link decision with whoever owns the ABI production site
      (`20_EMBEDDING_WITH_ABI.md`). *(Phase 10 of this plan; no-cross-link already
      confirmed — same team owns both.)*
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
      **Open item**: `actor_family`/`value_chain`/`size_class`/`entity_type` choice lists
      are not enumerated anywhere in `docs/05` or the original blueprint (only "CharField
      (choices)") — implemented with a placeholder provisional set (see docstring in
      `apps/sampling/models.py`) for engineering purposes. The PI must confirm or replace
      these against the actual approved sampling register before real Main-400 import;
      Province (10 Zimbabwe provinces + 2-letter codes) is objective fact, not a
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

- [ ] Implement `contacts`/`messaging` reminder queue per
      `12_CONTACT_CRM_AND_MESSAGING.md` (queued, never auto-sent beyond the approved
      sequence).
- [ ] Implement WhatsApp Business Platform integration once templates are Meta-approved.
- [ ] Implement `kii` app and frontend per `13_KII_MODULE.md`.
- [ ] Implement `evidence` app and frontend per `14_DOCUMENTARY_EVIDENCE_MODULE.md`.

## Phase 8 — Privacy, audit & exports

- [ ] Confirm every disclaimer from `18_DATA_PRIVACY_AND_COMPLIANCE.md` appears on every
      required screen.
- [ ] Confirm consent capture blocks data persistence until given.
- [ ] Confirm `AuditEvent` entries are created for every action listed in
      `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- [ ] Implement the de-identified analysis export and the full operational export
      (`06_API_ARCHITECTURE.md`), with an automated test asserting no identifying field
      appears in the de-identified one.

## Phase 9 — Testing pass

- [ ] Run the full backend test suite; all green.
- [ ] Run the full frontend component test suite; all green.
- [ ] Run the Playwright E2E suite (happy path, reserve-lock, ineligible-respondent,
      dashboard privacy) from `22_TESTING_STRATEGY.md`; all green.

## Phase 10 — Deployment prep & staging rehearsal

- [ ] Write Nginx config and `systemd` units per `23_DEPLOYMENT_ARCHITECTURE.md`.
- [ ] Stand up the staging environment against the dedicated Kobo test asset.
- [ ] Run the backup/restore drill against the RPO/RTO targets.
- [ ] Rehearse the full go-live rollout checklist (`23_DEPLOYMENT_ARCHITECTURE.md`) on
      staging with synthetic cases only.
- [ ] Conduct user acceptance testing with PI, Field Coordinator and one RA.

## Phase 11 — Go-live

- [ ] Verify `28_DEFINITION_OF_DONE.md` in full, including the 15-item go-live checklist.
- [ ] PI sign-off.
- [ ] Issue the first live Main-400 invitations.
