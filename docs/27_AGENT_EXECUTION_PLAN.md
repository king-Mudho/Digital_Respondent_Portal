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

- **Cross-stratum Main↔Reserve pairing — allowed, flagged, open to tightening
  (2026-09-13).** The matched-case picker offers same-stratum Reserves first but does not
  *refuse* a cross-stratum pairing: there may be no same-stratum Reserve left, and
  substituting across strata is a sampling judgement for the PI rather than something
  code should veto. It is never silent — the dropdown labels it, the screen warns, and
  the `AuditEvent` records `same_stratum: false`. If the PI would rather it were blocked
  outright, that is a one-line change in `sampling.services.set_matched_case()`.
  `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` does not state a rule either way, which is why
  this is recorded here rather than decided silently.

- **PROIT ethics/change-control review — open, deliberately (2026-09-12).** Respondent-
  facing PROIT is live on the PI's own documented **risk acceptance**, not on an ethics
  or change-control clearance; the supervision letter offered as sign-off predates the
  PROIT specification and cannot serve as approval for it. See the PROIT section below
  and `30_PROIT_MODULE.md`. If a supervisor or ethics body reviews PROIT later, record it
  as a new event — do not retrospectively relabel the risk acceptance as a clearance.

- **Phase 0 — POTRAZ / Data Protection Officer determination. RESOLVED (2026-09-12).**
  `18_DATA_PRIVACY_AND_COMPLIANCE.md` specified the compliance question; the PI's
  determination is that Chinhoyi University of Technology's Research Ethics Clearance
  (Annex 19, Form GRSD 17 SEBS/06/2025, approved 24.08.2026) and the study's operation
  under the University's institutional research governance covers this position — see
  `18_DATA_PRIVACY_AND_COMPLIANCE.md` for the full record. No longer blocks Phase 11.
- **Phase 0 — QA rule threshold values. REVIEW PACK ISSUED (2026-09-13), sign-off still
  open.** `15_QA_AND_DATA_QUALITY.md` proposes concrete engineering defaults (e.g. 5–90
  minute plausible duration window) precisely so the PI has specific numbers to confirm
  or adjust rather than an abstract placeholder. Treat these as provisional until the PI
  signs off. `31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md` Part A now sets out each value, what
  it does, and the consequence of setting it too high or too low, in a form a reviewer
  can sign. Preparing it surfaced that only three of the nine thresholds are actually
  evaluated: five are dormant until the real Kobo field list exists, and
  `mode_imbalance_alert_ratio` is defined but never read by `evaluate_submission()` —
  either implement it or remove it, because as it stands it implies a control that does
  not exist.
- **Phase 5 — PIS wording. REVIEW PACK ISSUED (2026-09-13), sign-off still open.** See
  the Phase 5 entry below for the drafting history. `31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md`
  Part B reproduces the live v1.1 text and lists seven gaps an ethics reviewer is likely
  to raise. The most material: **the PIS does not disclose PROIT background research.**
  The verification screen explains it at the point of use, but the information sheet the
  respondent consents on the basis of does not mention that the team may have compiled a
  profile of their organisation beforehand. That is a consent question, not a UI one.
- **Phase 0 — visual palette.** `21_UI_UX_GUIDELINES.md` proposes a blue/neutral
  academic palette distinct from ABI's green/gold, pending sponsor/PI confirmation.
- **Phase 0 — Shona/Ndebele Participant Information Sheet.** `19_LANGUAGE_AND_
  ACCESSIBILITY.md` flags this as a low-cost mitigation worth considering even within
  the English-only v1.0 interface decision — PI to confirm whether to produce translated
  PIS documents ahead of Phase 1.
- **Phase 0 — developer/team assignment.** Not a specification question but a staffing
  one: who builds this, given the September 2026 Phase 1 target has little runway left
  by the time this plan is approved.

- **Phase 11 pre-go-live audit-log review — two verification artefacts, not real
  respondent activity (2026-09-13).** The production `AuditEvent` table contains two
  entries that will otherwise look like a compliance problem at the go-live review:

  | When (UTC) | Action | Object | Case |
  |---|---|---|---|
  | 2026-09-13 19:17:30 | `invitation.issued` | `InvitationToken` 7 | `SID-2026-000801` |
  | 2026-09-13 19:17:30 | `consent.recorded` (GIVEN, PARTICIPATION) | `ConsentRecord` 6 | `SID-2026-000801` |

  Both were produced by an end-to-end check that the newly added consent gate on
  `POST /api/v1/appointments/` actually holds against the live deployment (it does:
  `403 consent_required` before consent, `201` after). The token, consent record and
  appointment they refer to were deleted immediately afterwards, so these two rows now
  point at objects that no longer exist, and no `Respondent` sits behind the consent.

  The audit entries were deliberately **not** deleted: they record actions that genuinely
  occurred, and editing the audit trail to tidy away operational activity is precisely
  what that log exists to prevent. Read them as deployment verification dated before
  fieldwork opened — no real respondent was invited or consented on 2026-09-13, and the
  operational tables were verified empty afterwards (0 tokens, 0 consents, 0 appointments,
  128 respondents, 801 sample cases).

  *Lesson for future live verification: prefer a rolled-back transaction (as used for the
  eligibility-gate check the same day, which left no trace) over real HTTP calls against
  production whenever the gate can be exercised at the service layer.*

- **Audit trail edited on 2026-09-22 (needs the PI's acknowledgement).** `AGENTS.md`
  ground rule 1 says not to edit audit events to tidy away one's own actions. On the PI's
  explicit request in chat, 45 `AuditEvent` rows had their `user` field filled in and a
  note added to `metadata`: 7 rows written by the cleanup itself (first recorded with no
  user because they were run through the database shell) and 38 older rows whose own
  metadata already named the acting user (`user_id`, `issued_by_id` or `by_user_id`).
  Every original value (`action`, `object_type`, `object_id`, `from`/`to`, reasons,
  timestamps) is untouched; the only additions are the `user` field and a `reattributed`
  or `backfilled` key stating what was done and when. Nothing was deleted from the log.
  This is still an edit to the trail and goes further than the rule allows, so it is
  recorded here rather than left implicit. To list every affected row, filter
  `metadata` for those two keys. Three `invitation.issued` rows could not be attributed
  (no issuer recorded, or issuer account no longer exists) and were left blank.
- **`AGENTS.md` ground rule 1 is out of date.** It says "No invitation has been issued
  yet". Invitations were issued from 2026-09-16 onward, so the sentence should be
  corrected by the PI, who owns that file.

- **`kudzai` admin account (user 120). RESOLVED (2026-09-28): the PI decided to keep it, at the
  PI / System Admin role, and nothing was changed.** An account with
  the PI / System Admin role, email `kudzaimano0@gmail.com`, exists and added two contacts
  on 2026-09-24 (both since removed as test entries). That role can do everything the PI's
  own account can, including managing users. It was left exactly as found while the question
  was open; the PI's decision to keep it, at that role, is recorded here.

- **Supervisor named on the "Confirmation of PhD Supervision" letter — still open
  (2026-10-01).** All four clearance/approval documents are now uploaded to production
  (see below), but the supervision confirmation letter still names only Dr L. Chikazhe,
  dated 20 August 2026 -- re-checked against the actual PDF content when it was uploaded,
  not assumed unchanged. Dr J. Kanyepe appears as co-supervisor elsewhere in this system
  (the Participant Information Sheet and prior ethics-pack text). No second letter has
  been supplied yet. This document was created with `is_public=False` and should stay
  that way until either a second letter covering Dr Kanyepe is found (publish both
  together) or the PI confirms this single letter is sufficient as-is.

- **The KII self-service information screen reused the Main-400 Participant Information
  Sheet verbatim, and its wording described "the questionnaire" — RESOLVED (2026-10-01).**
  Flagged when the KII self-service feature shipped, left unchanged at the time rather
  than drafting replacement wording unilaterally (a PIS wording change needs the PI's
  sign-off, not an engineering judgement call). The PI then directed drafting KII-specific
  wording and deploying it. A new, separate `KII_PARTICIPANT_INFORMATION_SHEET` (version
  `KII-v1.0`, own file `frontend/lib/constants/kiiParticipantInformation.ts`, own sign-off
  row in `docs/31` Part B-KII) now serves `/ki/[token]/information` — only the "what taking
  part involves" paragraph was rewritten, describing a Key Informant Interview with the
  real duration figures from the live KoboToolbox KII Guide rather than a questionnaire;
  every other paragraph carries over from the Main-400 sheet unchanged. See "Drafting the
  KII-specific Participant Information Sheet" below for the full record.

- **KII RA accounts need their own KoboToolbox collaborator login for the KII Guide
  project — raised with the PI before this session, never actually written down here
  until now (2026-10-01).** The staff-side "Continue this interview" button
  (`/admin/kii/[id]`) opens the KII Guide form directly; a logged-in KII RA without their
  own Kobo access to that specific project would hit the same KoboToolbox sign-in wall
  the anonymous self-service link hit before its `add_submissions` permission was added
  (see "Verifying all three KoboToolbox links end to end" below). Granting a named
  collaborator account per RA (not widening anonymous access, which is already granted
  and is a different, broader permission) is a KoboToolbox project-settings action for
  whoever administers that project, not something fixable in this codebase.

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

## PROIT — pre-interview profiling module (2026-09-12)

The PI provided `ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx` and, after a read-and-
summarise pass, directed that it be built. Not part of the original Phase 0–11 plan; a
controlled add-on, specified in full in `30_PROIT_MODULE.md`.

- [x] `backend/apps/proit/` — models for the three-value architecture (documentary value,
      respondent's own answer, researcher-reconciled value, kept permanently separate and
      never merged), evidence records with source/date/locator/confidence and a four-tier
      source-authority hierarchy, `EVID-<5>` identifiers.
- [x] Admin pre-profile panel (`components/admin/PreProfilePanel.tsx`) on both the sample
      case and KII detail pages, with the source-authority tier selector.
- [x] KII adaptive gap engine — generates interview questions only for genuinely
      unresolved gaps (KNOWN / VERIFY / UNKNOWN / CONTRADICTION / PROBE).
- [x] Researcher review-and-lock screen (`/admin/proit/[id]`).
- [x] Respondent verification screen (`/i/<token>/verify`), inserted after consent and
      before the completion-mode choice. Self-skips entirely when there is nothing to
      verify, so the flow is unchanged for a case with no locked pre-profile.
- [x] Enforced in code: PROIT can never pre-fill, skip or infer a frozen
      ABI/NFM/Digital-Readiness/FST scale item — only non-core descriptive background.

**Governance.** The source document called itself "subject to supervisor/ethics
change-control decision". The PhD supervision letter offered as that sign-off is dated
20 Aug 2026 and predates the PROIT specification (12 Sep 2026), so it cannot serve as
approval for it — this was raised rather than accepted. The PI then chose to make their
own documented risk-acceptance decision, and respondent-facing PROIT was enabled behind
`PROIT_ENABLED_FOR_RESPONDENTS` on that basis. It is recorded in `30_PROIT_MODULE.md` as
a **PI risk acceptance, not an ethics or change-control clearance**; if a supervisor or
ethics body reviews PROIT later, that is a new event and not a retroactive fix to this
one.

## Second audit pass — roles, registers, respondent flow (2026-09-13)

Commissioned as a deep end-to-end audit: fix broken screens and flows, ensure every
screen has working controls, and scope each role's navigation to its own modules. Every
item below has a regression test, and where a test already existed but was passing for
the wrong reason that is stated — those were the more dangerous cases.

**Access control — two documented controls that did not exist**

- [x] **The eligibility gate was never enforced.** `kobo.services.build_redirect_url()`
      documented itself as issuing no questionnaire URL "without a passed eligibility
      check and GIVEN participation consent", and `28_DEFINITION_OF_DONE.md` had the
      corresponding item ticked. Only consent was checked. `/api/v1/consent/` is
      `AllowAny` with a valid token as its only credential, so anyone the eligibility
      screen turned away could POST consent directly and receive a Kobo URL. The test
      that appeared to cover this passed only because it never gave consent — its own
      comment said so. Fixed via `contacts.services.has_passed_eligibility`; the test now
      consents first, which is what a bypass looks like.
- [x] **`IsQAOrAdmin` was shared across three unrelated modules**, so a KII RA could edit
      documentary evidence and a Documentary RA could take QUAN QA decisions. Split into
      `IsQAOrAdmin` / `CanManageKII` / `CanManageDocuments`.
- [x] **The KII/document dashboard excluded its own RAs** — it used `IsAnalystOrAdmin`,
      refusing the KII and Documentary RAs that `18_DATA_PRIVACY_AND_COMPLIANCE.md`
      grants it to. Now `CanViewKIIDocumentDashboard`.
- [x] **Appointment requests are now consent-gated** (PI decision). An appointment records
      a named person's availability against an identified organisation and puts them on an
      RA's call list, so it sits behind the same gate as the self-administered route.
- [x] **`matched_case` had no validation** — the API would accept a Main paired to another
      Main, a case paired to itself, or one Reserve claimed by two Main cases, the last
      silently breaking the reserve lock. Now routed through
      `sampling.services.set_matched_case()` with an audit entry.

**Role-scoped navigation**

- [x] `backend/api/navigation.py` added as the single source of truth for role → screens,
      served by `GET /api/v1/auth/me/`. Previously all 14 nav links showed to every role
      and everyone landed on `/admin/dashboard`, which four of the eight roles are
      refused. Each role now lands on its own first screen, and a screen outside the role
      renders an explicit card rather than a page whose every fetch 403s.
- [x] In-page gates (`WriteOnly` / `ReadOnly` / `IfScreen` / `IfRole`) so read-only roles
      stop seeing write controls that 403 on submit.
- [x] `seed_drp_dev` now creates one account per role, so this is checkable in a browser.

**Missing and unusable screens**

- [x] `/admin/dashboard/qa` built — `/api/v1/dashboards/qa/` had existed since Phase 6
      with nothing consuming it and no nav link to it, so the QA dashboard specified in
      `16_DASHBOARDS_AND_REPORTING.md` simply did not exist in the UI. Phase 6's own
      checklist item ("all six dashboards") was satisfied by five plus an endpoint.
- [x] Pagination and `?search=` across every register. Page size is 20 against 400 Main +
      400 Reserve + 90 KII + 100 documents, and no register had a paging control, so every
      row past the first twenty was unreachable from the UI.
- [x] `KIIRecord` and `DocumentRecord` querysets explicitly ordered — unordered pagination
      makes page boundaries arbitrary, so a row could appear on two pages or none.
- [x] Matched-Reserve picker on the case detail page, replacing a Django admin workaround.

**Respondent flow**

- [x] Every step reported failure — each previously used `try/finally` with no `catch`, so
      a failed request left the button re-enabled and the page unchanged. Worst on
      consent, where the respondent could not tell whether their decision had registered.
- [x] Appointments can no longer be requested in the past (picker, page, and server).
- [x] PROIT verification submits sequentially rather than via `Promise.all`, which had
      stranded the respondent mid-way on a partial failure; a skip option added.
- [x] The Kobo handoff offers a retry and an assisted-completion route instead of being a
      dead end on error.
- [x] Someone who booked a call is no longer told they have finished participating.

**Infrastructure**

- [x] Sign-in given its own throttle scope. It shared the generic `anon` 30/minute bucket
      with the public respondent endpoints, so a team behind one office NAT competed with
      respondent traffic — and DRF's 429 reached the login screen as "Invalid username or
      password". Found because the new role-navigation E2E spec exhausted the shared
      bucket; the suite was reproducing a real deployment condition.
- [x] The error envelope surfaces the first field error as `message`. A DRF
      `ValidationError` has no top-level `detail`, so every validation failure returned
      "An error occurred." — useless to the respondent flow, which has no field-level UI.

Backend 260/260, Playwright 26 specs (25 run, 1 skipped), `ruff`, `tsc --noEmit` and
`eslint` clean. All deployed to production and verified live. `README.md`, `AGENTS.md`,
`docs/18`, `docs/28`, `docs/INDEX.md` and the end-user guide were updated in step.

**Data-hygiene note.** `SID-2026-000801`, a duplicate MAIN case created via the UI on
2026-09-12 against an organisation whose register role is RESERVE (`SID-2026-000676`),
was deleted on the PI's instruction on 2026-09-13 — no import provenance, no dependent
records, and it was inflating the Main count to 401. Its organisation was kept, since it
legitimately backs the Reserve case. An `AuditEvent` records the deletion and its reason.
Production is back to 400 Main / 400 Reserve, all 400 paired.

## Test-data cleanup, PROIT to KoboToolbox, AI cost and audit changes (2026-09-21 / 22)

**What was built and deployed** (each change tested, deployed and checked on production;
backend 565 tests, frontend 8, Playwright 60 tests of which 3 skipped by design):

- [x] PROIT profiles are sent to a fourth KoboToolbox form, "ABF-FST PROIT Interview
      Profile" (asset `aWZH7brfEnaYvoDs5rJvh2`), once, when a profile is reconciled or a
      protocol deviation is recorded (`apps/proit/kobo_submit.py`, retried by a Celery
      task; `manage.py push_proit_to_kobo` re-sends). The form definition lives in
      `apps/proit/kobo_form.py`; `deploy/kobo/build_proit_form.py` builds the XLSForm from
      it. Verified live for a questionnaire case and a KII: every documentary, respondent
      and reconciled value matched what KoboToolbox held; the test records were removed
      from KoboToolbox afterwards and the database changes rolled back.
- [x] PROIT desk research runs on Sonnet 5 with prompt caching (`AI_PROIT_RESEARCH_MODEL`);
      document coding stays on Opus 5. A live search on Opus 5 returned 23 proposals for a
      real organisation. Sonnet 5 has **not** yet been compared with it on a live run, and
      the Anthropic credit balance ran out during verification, so the live AI steps were
      not re-run afterwards.
- [x] An empty AI credit balance is reported in plain words instead of the provider's raw
      error.
- [x] `log_action(..., user=)` accepts the acting user directly. Background tasks, exports,
      bulk moves and invitations recorded their user only in metadata because the
      request-bound thread-local is empty outside a request, so `AuditEvent.user` was blank
      for real actions. Fixed for those seven call sites.
- [x] The Audit Log screen shows a plain-English label and a one-line detail; the raw code
      is a hover tooltip. A test fails if a new action code is added without a label.
- [x] `manage.py check_test_data_smells` and a daily 06:00 (Harare) email to the PI admins
      flag likely test data. Read-only.
- [x] Study contact email changed from `abffst.research.cut@gmail.com` to
      `abffst.research@gmail.com`; Participant Information Sheet bumped to v1.4 with a
      sign-off row in `docs/31`. **Still open:** the Gmail App Password for the new address
      has not been installed, so outgoing mail still sends from the old account until
      `deploy/configure-email.sh` is run by the PI.

**Test-data cleanup on production (2026-09-22).** The PI confirmed each step in chat. A
backup (`drp-20260922-080238.sql.gz`) was taken first. Before deleting anything the
registers were checked: 800 organisations and sample cases, 90 KII records, 100 document
records and 137 respondents are the imported real data and **none of them was deleted**.
What was removed was operational data created by trying the system out:

- 7 pre-interview profiles (on SID-2026-000001, -000002, -000003, -000016, -000062,
  KII-0001, KII-0090) with 88 dependent rows (32 evidence sources, 29 AI proposals, 19
  fields, 1 research run). Their one KoboToolbox record was already gone from the form
  when deletion was attempted.
- The uploaded files and AI drafts on DOC-0001 and DOC-0007 (removed through the existing
  audited service); DOC-0001's coding decision reset to Pending / Unverified.
- 3 invitations (SID-2026-000001, -000062, -000399), all 11 consent records, the
  reconciled test questionnaire submission on SID-2026-000062 with its QA decision, 4
  cached KoboToolbox copies (one named `TEST-DELETE-ME-0002`), and 3 respondent contact
  rows on SID-2026-000399 (removed at the PI's explicit request).
- SID-2026-000001, -000062 and -000399 reset to S03, the baseline of the other Main cases;
  KII-0001 reset to Prospect / Not started.
- SID-2026-000399 was first treated as a live respondent because it showed a started
  survey and consent; the PI then confirmed it was test data and it was reset.
- KII-0068 and KII-0083 were not duplicates. Both carried the PI's name from the import
  instead of the "(contact not yet identified)" placeholder; corrected to
  "GigaFood One (contact not yet identified)" and "Proagromark Investments (contact not
  yet identified)". Nothing was deleted.

The dashboard read 0/400, 0/60 and 0/50-75 afterwards; the PI confirmed on screen. The
cleanup entries are in the audit log (see the Open question above about how they were
attributed).

**Left as found, waiting for the PI:** an empty pre-interview profile on SID-2026-000002
(created 2026-09-22 09:56), a respondent contact on SID-2026-000001 whose email matches a
staff account, and SID-2026-000003, where a Field Coordinator issued an invitation at
09:59 and revoked it at 10:31. All three were flagged by the smell check and none was
changed.

**Verification note.** Live verification used rolled-back transactions for database
changes. The KoboToolbox writes (three test records and six throwaway projects created
while building the PROIT form) were removed through the API, but they cannot be rolled
back, so they are listed here.

## Test-data cleanup, second round (2026-09-28)

The PI asked for the information entered on 2026-09-24 to be reset. Every step was
scoped from a read-only look first, guarded in code, and confirmed in chat. A backup
(`drp-20260928-070603.sql.gz`) was taken first. The production registers were checked
before each deletion: all 800 organisations, 800 sample cases, 90 KII records, 100 document
records and the imported respondents were left alone.

**What the audit log shows.** The 24 Sep entries (contacts added, invitations issued and
revoked, consents, QA decisions) are attributed to the PI's own account, `happyson`, not
to the Field Coordinator's, so either that login was shared or the PI made them. Nothing
here depends on which.

**Removed:**

- [x] Six cases returned to S03: SID-2026-000006 (was S05), -000027 (S10), -000028 (S10),
      -000029 (S06), -000017 (S06) and -000003 (S05, invitation revoked on 22 Sep). Their
      assignment to the Contact RA was kept.
- [x] 10 invitations, 3 consent records, 9 contacts (all created 24 Sep) and 2 questionnaire
      submissions that had passed QA (with their QA decisions and 2 cached copies) from
      those cases. The two submissions were also **deleted from KoboToolbox** through the
      API after each was checked against its Sample ID; the questionnaire form there now
      holds 0. That deletion cannot be rolled back.
- [x] SID-2026-000803 and its organisation, "Ministry of Agriculture Mechanism Water
      Resources Development": a hand-made MAIN case created 2026-09-24 12:02 with no import
      provenance, no Reserve pairing and nothing attached, which made Main 401. Deleted on
      the PI's instruction, the same kind of case as SID-2026-000801 on 2026-09-13. Main is
      back to 400 and Reserve to 400.
- [x] Two contacts on SID-2026-000001 (17 Sep) in a staff member's own name, one with his
      own phone and email; and empty test pre-interview profiles #19 (SID-2026-000002) and
      #20 (SID-2026-000135, whose only AI research run had failed on the empty credit).

The dashboard reads 0/400, 0/60 and 0/50-75, all Main cases are at S03, and the go-live
preflight passes 15/15.

**Audit trail.** Nothing was edited this time. Each step wrote a new `AuditEvent` under the
PI's account with the reason and the words "run by the assistant" (possible now that
`log_action` accepts the acting user), so nothing needs re-attributing afterwards.

*A guard did its job:* the run that removed the SID-2026-000001 contacts first stopped on
its own assertion, because the contact turned out to date from 17 Sep and not 22 Sep as
assumed. Nothing had been changed; the guard was corrected and the run repeated.

## Participant Information Sheet v1.5 and AI use (2026-09-28)

The PI reported that the supervisors, the ethics office, the data-protection position and the AI
provider's terms had all been checked and confirm the use of AI described in the ethics pack, and
told the assistant to proceed.

- [x] Participant Information Sheet bumped to **v1.5** (`frontend/lib/constants/participantInformation.ts`):
      one paragraph added after the public-information paragraph saying an AI tool from a company
      outside Zimbabwe helps with that search, that it is given the organisation's details and the
      respondent's name and job title but never a phone number, email address, questionnaire answer or
      interview content, and that a researcher checks everything it finds. No other wording changed.
      Every consent recorded from now on carries `v1.5`; none had been recorded under v1.4.
- [x] `docs/31` updated (current version, the quoted text, and a v1.5 sign-off row, with the v1.3 and
      v1.4 records left as they were). The manuals (v1.12), including the Respondent Guide, and the
      README carry the new version and a line about the AI tool.

**What this record does not prove.** The confirmations are recorded on the PI's statement in chat. The
portal holds no copy of them, so the PI should keep the supervisors', ethics office's and data-protection
confirmations, and the provider terms that were read, on file with the study's ethics papers. The
methodology chapter and thesis declaration still need the PI's own wording (drafts are in the ethics pack).

**Not changed.** The respondent-facing "Before we continue" verification screen still says the team
reviewed publicly available information and does not mention the AI tool; the information sheet, shown
before consent, is where the disclosure is made.

## Research Clearance screen (2026-09-30 / 2026-10-01)

The PI attached four official approval/clearance documents and a general-purpose
re-implementation prompt. Most of what that prompt described already exists, built and
tested in Phases 0-10; the one genuinely new, well-scoped thing it pointed at was a way
for a respondent to check the study is real before answering anything — not previously
specced in `docs/00`-`28`.

- [x] New `backend/apps/clearance` app: `ClearanceDocument` model (title, issuing body,
      type, reference number, issue date, description, a private file, `is_public` and
      `active` flags, both defaulting so nothing is shown until explicitly switched on).
      Private file storage follows the existing `apps/evidence` pattern (never web-served
      directly, served only through a permission-checked, audited view) rather than
      sharing code with it, matching how the rest of this codebase keeps each app's file
      handling self-contained.
- [x] Admin screen `/admin/clearance` (PI_ADMIN only, registered in
      `backend/api/navigation.py` and covered by the `SCREEN_ENDPOINTS` reachability test
      per `AGENTS.md` ground rule 10): add a document, upload/replace its file, toggle
      `is_public`/`active`.
- [x] Respondent-facing section on the information step of the invitation flow
      (`frontend/app/i/[token]/information/page.tsx`), token-gated like every other
      respondent endpoint, rendering nothing at all when no document is public.
- [x] Once a document has ever been shown to a respondent (`is_public` was ever true, or
      an `AuditEvent` shows its file was actually fetched) it can't be deleted via the API,
      only hidden — the admin UI disables the button too, but the server is the actual
      boundary, per `AGENTS.md`'s "frontend declining to route somewhere is not a control."
- [x] 18 backend tests, mutation-tested against all 4 safety rules. Two tests were
      rewritten mid-mutation-testing: they used a `file_ref` string with no real file on
      disk, so a broken permission check still 404'd for the wrong reason (`open_file()`
      raising "missing on disk" before the permission check ever ran) and could not have
      caught a real bypass — exactly the "a test that cannot fail is worse than no test"
      trap this file already warns about. Fixed with a real file written to `tmp_path`.
- [x] One Playwright e2e spec driving the full admin-to-respondent round trip in a real
      browser. Three bugs were found and fixed in the test itself (the feature was already
      correct): a row locator matching the wrong nested `<div>`; `.check()`/`.uncheck()`
      not working on a checkbox whose state is query-cache-controlled rather than native,
      which snaps back before the mutation resolves; and page-wide text assertions that
      broke once a prior run's own permanently-public document (an intended consequence of
      the no-delete-once-public rule) was still showing.
- [x] Full backend suite (603 tests) and frontend typecheck/lint/build re-run clean before
      deploying.
- [x] Deployed to production (2026-10-01): `git archive HEAD | gzip`, scp'd to the server
      and extracted into `/srv/agribiz-drp`, then `deploy/deploy.sh` — backup taken first,
      `clearance.0001_initial` migration applied, frontend rebuilt, all four services
      restarted, all three health checks (backend, frontend, through nginx HTTPS) passed.
      Verified live: the admin API refuses unauthenticated access (401), the respondent
      endpoint refuses a request with no token (400), and `/admin/clearance` renders.
- [x] Uploaded the four PI-supplied documents to production (2026-10-01): Research Ethics
      Clearance Letter (id 2), Approval of Research Proposal — Ministry of Agriculture,
      Mechanisation and Water Resources Development (id 3), Clearance and Support for the
      Research Project — same Ministry (id 4), Confirmation of PhD Research Supervision
      (id 5). Done at the service layer (`apps.clearance.services.save_file`, a
      `manage.py shell` script, not the admin web UI — this agent does not hold or enter
      the PI's production login) after a fresh backup, attributed to the PI's own account
      (`created_by`/audit `user_id` both 6, `happyson`), with the same two `log_action`
      calls (`clearance.document_created`, `clearance.file_uploaded`) the real admin
      upload flow makes. All four created with `is_public=False`.
- [x] PI confirmed which to publish (2026-10-01): the ethics clearance letter (id 2) and
      both Ministry letters (ids 3, 4) are now `is_public=True` — same service-layer
      approach, the same `clearance.visibility_changed` audit event the admin PATCH
      endpoint fires, attributed to the PI's account. Confirmed live via
      `RespondentClearanceDocumentSerializer` that exactly these three are returned, with
      no case/respondent data. The supervision-confirmation letter (id 5) stays
      `is_public=False`, per the open question above.
- [x] **Found and removed an orphaned row (id 1), 2026-10-01.** While re-checking the
      register at the PI's request (asked to "sign in and confirm it looks right" — this
      agent cannot sign in to production; checked the same data the admin screen renders
      instead), a fifth, file-less duplicate "Research Ethics Clearance Letter" turned up,
      `is_public=False` from creation to discovery. Its own audit event
      (`clearance.document_created`, id 713, 15:19:16 UTC) timestamped 25 seconds before
      the real id 2's row — exactly the gap from the very first upload-script run, which
      created the record, then crashed on a file-permission error (the `/tmp` staging
      directory wasn't yet world-readable) before `save_file()` ever ran. Confirmed
      `is_public=False` and no `file_ref` before deleting (AGENTS.md's guard-before-delete
      convention); the row itself is gone, its audit event is not — the rule this project
      holds to is leaving the trail alone, not erasing the record of a mistake. No
      respondent could ever have seen this row.
- [x] `README.md`, `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` and the user-guide manuals
      (`docs/tools/manuals/*.js`, rebuilt to v1.13 via `build_manuals.js` and
      `finalise_manuals.ps1`, verified by extracting text from the built PDFs) now describe
      the Research Clearance screen, per this file's "Keeping the documentation honest"
      section.

## Correcting an already-saved Organisation, KII record (2026-10-01)

The PI asked for an edit option "almost everywhere" a record is saved — Organisation,
Main-400, KII Register, Documents were named specifically, with "correct the actual name
of the organisation" as the concrete example. Checked each before building anything:
Documents already had a working edit form (`DocumentRecordDetailView` + the record-details
panel on its page); Organisation had no edit path at all, anywhere; a Main-400 case's own
backend endpoint could technically take a PATCH but the screen only ever used it for
`assigned_ra`/`matched_case`; a KII record's endpoint was the same shape.

- [x] `OrganisationDetailView` (`GET`/`PATCH /api/v1/organisations/{id}/`): name, district,
      entity_type, value_chain correctable from `/admin/organisations` (inline Edit per
      row). province/actor_family/size_class are deliberately read-only through this
      endpoint — `resolve_stratum_for_organisation()` only resolves a case's
      `StratumDefinition` from these three fields once, at case-creation time, never again,
      so editing them afterwards would silently detach an organisation from the stratum its
      existing Main/Reserve pairing depends on (ground rule 4). The province code is also
      baked into the immutable `master_id`.
- [x] KII record "Record details" panel (`/admin/kii/{id}`): participant name, role,
      stakeholder category, preferred mode, interview date, duration, field notes —
      PATCHing the existing `KIIRecordDetailView`.
- [x] Main-400 case: no new edit surface added. Once Organisation correction existed there
      was nothing else on a case worth exposing — its other fields are either workflow
      state (already has validated, audited controls) or links that must not casually
      change (see the bug below). Correcting a case's organisation now means correcting the
      Organisation record itself.
- [x] **Two real gaps found while deciding what was safe to expose, neither previously
      exploited, both fixed and regression-tested** (mutation-tested: reverted each fix
      locally, confirmed the new test goes red, restored it):
      - `SampleCaseDetailView`'s PATCH had no handling at all for `organisation`/`stratum`/
        `sample_type`, unlike `matched_case` just above it in the same method — a bare
        request could have silently reassigned a Sample ID to a different organisation or
        flipped a case between MAIN and RESERVE, with no validation and no audit trail.
        These three can't be made `read_only_fields` on the serializer itself (it's also
        used by case creation, which needs them writable) — dropped from
        `validated_data` in `perform_update()` on PATCH only, the same pattern already used
        for `matched_case`.
      - `KIIRecordSerializer` left `status`/`transcript_status`/`coding_status` writable on
        the plain detail endpoint — a bare PATCH could have set `status=COMPLETED` directly
        and skipped `mark_completed()`'s recording-consent requirement entirely (ground rule
        6). Now read-only there; `KIIStatusTransitionView`/`KIITranscriptStatusView`/
        `KIICodingStatusView` remain the only validated, audited way to change them.
- [x] 6 new backend tests (`test_organisation_registration.py`,
      `test_sample_case_api_integrity.py`, `test_kii.py`). Full suite (609 tests) and
      frontend typecheck/lint/build re-run clean; both screens verified live in a browser
      against the local dev stack before deploying.
- [x] Deployed to production (2026-10-01): same `git archive | gzip` → scp → `deploy.sh`
      path as the clearance screen. No migration was pending (no new model fields — every
      field edited here already existed). Backup taken, frontend rebuilt, all four services
      restarted, all three health checks passed. Verified live: the new
      `organisations/{id}/` route exists and refuses unauthenticated access (401, not 404).

## KII self-service invitation link (2026-10-01)

The PI asked for a KII informant to be able to open a personal link themselves (WhatsApp/
email/SMS) and complete the interview alone, the same way a Main-400 respondent already
can — for someone who would rather fill it in in their own time than do a live call.
Before building, confirmed three protocol/consent decisions with the PI (AskUserQuestion,
per AGENTS.md § Open questions convention — these are research decisions, not engineering
ones): (1) no recording consent on this path, since nobody records an unsupervised
session; (2) a minimal information-then-consent flow, no organisation-confirmation step
(an informant was already identified by name by an RA, unlike an anonymous Main-400
organisation); (3) `INVITED → COMPLETED` as a valid direct status transition, since a
self-administered interview has no call to schedule.

- [x] `KIIRecord` gains `phone`/`whatsapp_number`/`email` (mirrors `contacts.Respondent`'s
      own contact fields). New `KIIInvitationToken` model + `apps/kii/services.py` token
      lifecycle (issue/validate/revoke, salted-hash-only storage, supersession on reissue)
      — a dedicated model, not an extension of `invitations.InvitationToken`: that model's
      status set (`ELIGIBILITY_PASSED`, `SURVEY_STARTED`, `QA_PASSED`, ...) is QUAN-shaped
      and consumed by QUAN-only code (reconciliation, dashboards, exports); reusing it
      risked the live Main-400 flow for no benefit, since KII's lifecycle is genuinely
      simpler (no eligibility concept, no SampleCase workflow to advance).
- [x] New public, token-gated endpoints under `kii-invitations/` and `kii-consent/`
      mirroring the Main-400 equivalents. `consent.services.record_consent()`/
      `has_given_consent()` already supported a `KIIRecord` from an earlier phase, and
      `kii.services.build_kii_coding_url()` already gated on participation consent and
      omitted participant-identifying data — both reused unchanged.
- [x] New respondent route `/ki/[token]/{information,consent,kobo-redirect}` — a separate
      namespace from `/i/[token]/...`, not a branch inside it, for the same
      don't-risk-the-live-flow reasoning as the backend. No "done" page, same as Main-400:
      opening the KoboToolbox form navigates away from the portal entirely.
- [x] KII record page gains an "Invite" panel (issue/reissue/revoke, ready-made WhatsApp/
      SMS/email messages) and the new contact fields on the existing "Record details" form.
      `InvitationSendPanel` (the Main-400 message-sending UI) now takes an optional
      `sendEmailPath` so one component serves both screens rather than a near-duplicate.
- [x] 20 new backend tests (`test_kii_invitations.py`) plus one rewritten test that had
      asserted the now-superseded "can't skip SCHEDULED" rule. The consent gate on the
      KoboToolbox redirect endpoint was mutation-tested (broken, confirmed the test went
      red, restored). Full suite (630 tests) and frontend typecheck/lint/build re-run
      clean. One Playwright e2e spec drives the whole path — an RA issuing the link from
      the KII record page, an informant opening it in a separate browser context (no admin
      session), through to a KoboToolbox redirect URL containing only the KII-ID — plus a
      second spec proving the redirect refuses before consent (403 `consent_required`).
      Both verified live in a browser against the local dev stack before deploying.
- [x] Deployed to production (2026-10-01): same `git archive | gzip` → scp → `deploy.sh`
      path as the previous two features. `kii.0003_kiirecord_email_kiirecord_phone_and_more`
      applied cleanly, all three health checks passed. Verified live: `kii-invitations/`
      validate refuses a missing token (400), issue refuses unauthenticated access (401),
      and the new `/ki/<token>` route renders.
- See the Open Questions section above for the one unresolved item this surfaced: the
  self-service information screen currently reuses the Main-400 PIS text verbatim, which
  describes "the questionnaire" rather than a KII interview.

## Verifying all three KoboToolbox links end to end (2026-10-01)

The PI asked, after the KII self-service feature shipped, to confirm every KoboToolbox
link actually works for a respondent opening it -- not just that the portal issues a
URL, but that the real Kobo form opens and the identifier prefills land where
reconciliation reads them. Tested all three directly: loaded the real public URL fresh
(a new browser context each time, matching how a respondent encounters it) with the
exact `?d[...]=` query the portal constructs, then inspected the actual form field
values via the rendered page, not just that the page returned 200.

- [x] **Main Study Questionnaire** — opens with no login. `d[sample_id]=`/
      `d[administration_mode]=` land correctly in `SAMPLE_ID_FINAL` (the exact field
      `apps.kobo.services.FORM_SAMPLE_ID_FIELD` reads) and `ADMIN_MODE_FINAL`
      (correctly translated from the portal's numeric code to the form's own choice
      name, e.g. `01` → `web_portal`). The "FIELD-NAME ASSUMPTION" flagged as unverified
      in that module's docstring since before a real Kobo asset existed is confirmed
      correct in production; the docstring's caution is now stale but harmless.
- [x] **Document, Digital Platform & Media Analysis Tool** — opens with no login,
      `d[section_a/DOC_ID]=` lands correctly.
- [x] **Main Study KII Guide — found broken, fixed.** The link redirected to a
      KoboToolbox *login page* instead of the form, confirmed in a clean browser context
      with no cached session. Root cause, confirmed via the KoboToolbox API (the same
      token already configured for reconciliation, not a new credential): the
      Questionnaire and Document Tool Kobo projects both grant the anonymous/public user
      `add_submissions`; the KII Guide project granted it to no one. **This is a real gap
      in the KII self-service feature shipped earlier today** — it was built and tested
      against the portal's own token/consent/redirect logic without separately verifying
      the underlying Kobo project's sharing settings permit an anonymous informant to
      actually reach the form. Flagged to the PI as a KoboToolbox project-configuration
      change (not something fixable in this codebase), who made the change directly.
      Re-verified immediately after in a fresh browser context: the form now opens with
      no login, and `d[part_a/KII_ID]=` lands correctly in `part_a/KII_ID`.
- **Still separately open, newly recorded here** (see Open Questions above): a KII RA's
  own staff-side "Continue this interview" button needs the RA to hold their own
  KoboToolbox collaborator login for this project — a different, narrower permission
  than the anonymous-submission one just fixed. Not touched in this pass; not previously
  written down anywhere in this file despite being raised earlier in conversation with
  the PI, so recorded properly now rather than left as something only this agent
  remembered.

## Drafting the KII-specific Participant Information Sheet (2026-10-01)

The PI directed drafting KII-specific wording for the self-service information screen
(not reusing the Main-400 sheet) and deploying it.

- [x] New `KII_PARTICIPANT_INFORMATION_SHEET` / `KII_PARTICIPANT_INFORMATION_SHEET_VERSION`
      (`"KII-v1.0"`) in a new file, `frontend/lib/constants/kiiParticipantInformation.ts` —
      a separate document and version line from `PARTICIPANT_INFORMATION_SHEET_VERSION`,
      not a shared constant bumped in place: the two sheets describe different things a
      participant agrees to, and `ConsentRecord.information_sheet_version` must point
      unambiguously at the exact text a given participant actually read. Conflating them
      would make that traceability wrong for whichever flow didn't just change.
- [x] Only the "what taking part involves" paragraph was rewritten — from "you will be
      asked to complete a questionnaire about your organisation" to a description of a
      Key Informant Interview, using the real duration figures on the live KoboToolbox KII
      Guide ("Standard duration: 30-45 minutes. Executive short form: 12-15 minutes.",
      read directly off the live form, not invented) and reframing who is being asked and
      why (knowledge/experience, not organisational selection). Every other paragraph
      (study/supervisors/ethics clearance, the PROIT/AI-research disclosure, voluntariness,
      no score/rating/financing decision, how contact details are kept, the contact line)
      carries over from the Main-400 sheet's current v1.5 wording unchanged. Deliberately
      does not mention recording: the self-service path is unsupervised by design, so
      nothing is ever recorded in that session.
- [x] `/ki/[token]/information/page.tsx` and `/ki/[token]/consent/page.tsx` updated to use
      the new constants instead of the Main-400 ones.
- [x] `docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md` gets a new, independent Part B-KII (text,
      rationale, gaps inherited from Part B, decision line) and its own sign-off row,
      rather than folding into Part B's existing v1.x history.
- [x] Verified live against the local dev stack before deploying: issued a fresh KII
      self-service invitation, opened it as the informant would, confirmed the new text
      renders on the information screen, gave consent, and confirmed directly against the
      database that the resulting `ConsentRecord.information_sheet_version` is `KII-v1.0`
      — not the Main-400 version string, proving the two are genuinely independent end to
      end, not just in the source file. Frontend `tsc`/`eslint`/`npm run build` all clean.
- [x] Deployed to production (2026-10-01): same `git archive | gzip` → scp → `deploy.sh`
      path as every other feature this session. Frontend-only change, no migration.
- [x] `docs/31` Part B-KII sign-off row recorded per the PI's instruction in this build
      session, same pattern already used for every other PIS version in this file.

## Manuals: covering the KII self-service flow (2026-10-01)

Checked the manuals for the KII self-service feature shipped earlier today and found
zero mentions anywhere — built and deployed without this pass at the time. The
Respondent Guide's own audience line ("organisations invited to take part") had
implicitly excluded KII informants entirely; a real informant opening a `/ki/...` link
had no guide describing what they'd see, and no KII RA Role Guide instructions existed
for the new "Invite" panel.

- [x] **Respondent Guide**: new chapter 7, "If you were invited to a Key Informant
      Interview" (old chapter 7 "Contact the research team" renumbered to 8) — the link
      pattern (`/ki/` not `/i/`), the shorter 4-step flow, and a tip covering the
      interviewer-assisted alternative. Points back to chapter 6's existing Q&A for
      what's shared (expired links, interruptions) rather than duplicating it.
- [x] **Role Guide 5 (KII RA)**: a new `can` bullet, and a new procedure section in
      `tasks.js` `T.kii` ("Sending the informant their own link (self-service)") covering
      entering contact details and using the Invite panel — flows automatically into both
      the System Manual's shared KII procedure section and this role guide, since both
      already draw on the same `T.kii` source.
- [x] **System Manual** §3.12: one sentence added describing the self-service option
      alongside the existing KII status-flow description, including that
      `INVITED → COMPLETED` is now a valid direct transition.
- [x] `common.js` `REVISION` bumped to **v1.14**. Rebuilt via `build_manuals.js` and
      finalised via `finalise_manuals.ps1` (System Manual 71→72 pages, Respondent Guide
      15→16, Role Guide 5 21→22) with no build failures. Verified by extracting text from
      the built PDFs, not by assuming the build succeeded: confirmed the new Respondent
      Guide chapter, the new Role Guide 5 procedure, and the System Manual sentence all
      actually landed.

## Manuals: covering Organisation/KII record correction, and a numbering bug found in the build source (2026-10-01)

Checked the System Manual against everything shipped this session and found a second,
older gap: the Organisation-editing and KII-record-editing screens (built and deployed
earlier in the day, before the KII self-service work) had never been documented in any
manual — same shape of gap as the KII self-service one just closed above.

- [x] `tasks.js` `T.registerOrg`: new "Correcting an already-registered organisation"
      section (Edit/Save/Cancel steps, plus a warn box explaining province, actor family
      and size class can't be corrected there because `resolve_stratum_for_organisation()`
      only resolves the stratum once, at case creation).
- [x] `tasks.js` `T.kii`: new "Correcting a KII record's details" section, inserted right
      after "Creating a KII record" (full Record details field set, plus a tip noting
      status/transcript/coding have their own separate controls).
- [x] `system.js` §6.7 (Organisations): sentence added mentioning correction.
- [x] **Bug found in the manual-building source itself, not the portal**: `system.js`
      built its Organisations section with
      `T.registerOrg.map((b) => (b[0] === "h2" ? ["h2", "7.3 Registering an organisation (PI, FC)"] : b))`
      — this overwrites the heading text of **every** `h2` in the block with the same
      literal string, not just the first. Adding a second `h2` to `T.registerOrg` above
      didn't get its own heading; it silently became a second, misnamed copy of the first.
      Caught by the same pypdf-text-extraction verification habit used throughout this
      project: "Correcting an already-registered organisation" was present in the rebuilt
      Role Guide 2 PDF (which numbers `T.kii`/`T.registerOrg` headings through a different,
      correct mechanism in `roles.js`'s `guide()`) but **absent** from the System Manual
      PDF. Fixed by using the existing `numberedSections()` helper instead — already used
      correctly elsewhere in the same file for `T.kii`, `T.documents` and
      `T.proitInterview` — which numbers the first `h2` with the given title and any
      further ones with a letter suffix (so this became "7.3a").
- [x] `common.js` `REVISION` bumped to **v1.15** (v1.14 was already committed and pushed
      in the previous pass, so this round needs its own version rather than silently
      amending a copy that may already be circulating). Rebuilt and finalised (System
      Manual 72→74 pages, Role Guide 2 52→53, Role Guide 5 22→23). Verified by extracting
      text from the rebuilt PDFs: "7.3 Registering an organisation (PI, FC)" and
      "7.3a Correcting an already-registered organisation" now both appear, each exactly
      once in the TOC and once in the body, with their own distinct section numbers; the
      KII side ("7.16a Correcting a KII record's details") was confirmed unaffected by the
      bug (it already used `numberedSections()`) and unaffected by the fix.

## Role Guide 1 (PI/Admin): missing organisation, KII, document and cost procedures (2026-10-01)

Asked to check the role guides too. Checked all 8 role-guide PDFs for the same features
(Research Clearance, organisation/KII correction, KII self-service invitation) and found
seven of them consistent with their own "You can" / "You cannot" lists. Role Guide 1
(PI/System Admin) was not: its "You can" list states "Do everything the Field Coordinator
can: register organisations, assign Contact RAs, verify cases in bulk, invite, activate
Reserves, record withdrawals, take QA decisions, manage KII and document records, log
costs" — but `roles.js`'s task list for guide 1 never included `T.registerOrg`,
`T.respondents`, `T.invite`, `T.kii`, `T.documents` or `T.cost`. The PI guide had no
step-by-step procedure anywhere for registering or correcting an organisation, creating or
correcting a KII record, sending a KII self-service link, adding or coding a document, or
logging a cost — a claim-without-a-control gap of the same shape AGENTS.md calls out for
code, just in a manual instead. This predates this session (the gap existed for `T.invite`
and `T.cost` before any of today's work), surfaced now by checking the guide against its
own stated capabilities rather than only against today's new features.

- [x] Added `T.registerOrg, T.respondents, T.invite` (after `T.bulkVerify`) and `T.kii,
      T.documents, T.cost` (after `T.clearance`) to Role Guide 1's task list in
      `roles.js`, mirroring Role Guide 2's existing use of the same blocks. No new content
      written — these are the same shared `tasks.js` procedures already used by the Field
      Coordinator and KII RA guides, so the newly-added organisation/KII correction
      sections from the previous entry above appear in the PI guide too, automatically.
- [x] `common.js` `REVISION` bumped to **v1.16**. Rebuilt and finalised (Role Guide 1
      52→71 pages; all others unchanged). Verified by extracting text from the rebuilt
      PDF: the guide's `4.x` task numbering now runs 4.1–4.36 with no gaps or repeats,
      and "Registering a new organisation and its sample case" (4.7), "Correcting an
      already-registered organisation" (4.8), "Creating a KII record" (4.14), "Correcting
      a KII record's details" (4.15), "Sending the informant their own link
      (self-service)" (4.18) and "Logging fieldwork costs" (4.27) each appear exactly
      once.

## AI cost baseline, and evaluating Meta's Muse Spark (2026-10-02)

The PI was shown a third-party chat proposing Meta's Muse Spark for PROIT, document coding and
pre-filling, plus extending the sample to 10,000 firms. Reviewed, and a supervisor brief written
(a private Artifact, not committed). Findings that matter to the build:

- The chat's claims about the portal were wrong: it read the public GitHub repo's `AGENTS.md`
  (the repo answers without login), not the database; `api.research...` and its endpoint list do
  not exist; `/bankability/check` would break ground rule 3.
- **No cost baseline existed.** On production: 0 of 101 document records held an AI draft, the
  `document.ai_draft_generated` audit entry carried no token counts, and the one `AIResearchRun`
  showed 0 tokens. A draft stores its own token counts, but drafts are discarded when a file is
  replaced or removed, so the numbers did not outlive them.
- [x] The audit entry now carries `tokens_in` / `tokens_out` (`evidence/tasks.py`), with a test
      that fails when the line is removed. Deployed to production 2026-10-02 (release
      20261002194341), preceded by a fresh `backup.sh`. Backend only, no migration.
- Meta's docs: Standard tier does not train on prompts; web search is a separate $2.50 per 1,000
  queries; PDF input is supported. Whether its Anthropic-compatible endpoint supports forced tool
  use, PDF blocks and streaming is **not documented and untested**. Third-party guides say
  access is US-only during public preview; the PI's account exists but its console asked for a
  payment method before any request.
- **Not done, and why:** a configurable `AI_DOCUMENT_CODING_BASE_URL` (so document coding could
  call Meta's endpoint) was written and then blocked by the session's safety check as redirecting
  document contents and the API key to another host. It was reverted, not worked around. Needs the
  PI's explicit go-ahead, ideally via the permission settings. PROIT is a larger job: its web
  search is an Anthropic server tool.
- [x] **PROIT recorded the wrong model.** `run_research()` called `AI_PROIT_RESEARCH_MODEL` but
      saved `AI_DOCUMENT_CODING_MODEL` on the `AIResearchRun`, so the run history named a model that
      never did the work. It went unnoticed because the two settings defaulted to different Claude
      models and nothing compared the record with the call. It would have put another provider's name
      on PROIT runs once the document model changed. Fixed (`proit/ai_research.py`), with a test that
      fails on the old line. Deployed to production 2026-10-02 (release 20261002195554), after a fresh
      backup; backend only, no migration. Earlier runs keep the name they were saved with; the one
      run on record is a failed one.
- A second attempt at the endpoint switch, made after the PI approved it in chat, was blocked by the
  session's safety check again and reverted. Only a change to the PI's permission settings clears it.
- PIS v1.5 already says the AI tool is "provided by a company outside Zimbabwe", so a provider
  change needs no new participant wording; the ethics position still has to cover Meta as the
  processor, which the PI says the supervisors have agreed.

## Phase 11 — Go-live

- [ ] Verify `28_DEFINITION_OF_DONE.md` in full, including the 15-item go-live checklist.
- [ ] PI sign-off.
- [ ] Issue the first live Main-400 invitations.
