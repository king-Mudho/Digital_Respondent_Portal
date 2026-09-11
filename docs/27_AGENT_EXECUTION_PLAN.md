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

- [ ] Create the two-folder repo layout (`frontend/`, `backend/`, `docs/`, `AGENTS.md`,
      root `README.md`) exactly as in `03_SYSTEM_ARCHITECTURE.md`.
- [ ] Scaffold `backend/` as a Django project with the `config/` and `apps/` structure
      from `08_BACKEND_ARCHITECTURE.md`; create all twelve empty apps.
- [ ] Scaffold `frontend/` as a Next.js + TypeScript project with the structure from
      `07_FRONTEND_ARCHITECTURE.md`.
- [ ] Add `.env.example` files (backend and frontend) exactly per
      `24_ENVIRONMENT_CONFIGURATION.md`.
- [ ] Set up `requirements/base.txt`, `dev.txt`, `prod.txt` and `frontend/package.json`
      with pinned versions from `04_TECH_STACK.md`.
- [ ] Set up Celery + Celery Beat scaffold (`config/celery.py`), no tasks yet.
- [ ] Set up the CI pipeline (lint, type-check, test stubs) per
      `23_DEPLOYMENT_ARCHITECTURE.md`.
- [ ] Confirm `python manage.py runserver` and `npm run dev` both boot cleanly with
      placeholder pages.

## Phase 2 — Core backend models & identifier/sampling control

- [ ] Implement `accounts`, `sampling`, `contacts`, `consent`, `invitations` apps' models
      per `05_DATABASE_ARCHITECTURE.md`.
- [ ] Implement `sampling.services.is_invitable()` and the reserve-lock enforcement path
      (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`, `AGENTS.md` ground rule 4).
- [ ] Implement Master_ID/Sample_ID generation exactly per
      `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`.
- [ ] Implement the S00–S16 workflow status state-transition table.
- [ ] Implement invitation token generation/hashing/expiry/revocation
      (`10_INVITATION_AND_CONSENT.md`).
- [ ] Run and commit initial migrations.
- [ ] Write the reserve-lock and token-lifecycle unit tests from
      `22_TESTING_STRATEGY.md` — these must pass before continuing.

## Phase 3 — Kobo integration & reconciliation

- [ ] Implement the `kobo` app: `QUANSubmission`, `ReconciliationLog`, Kobo API client.
- [ ] Implement the scheduled reconciliation Celery Beat task per
      `11_KOBOTOOLBOX_INTEGRATION.md`.
- [ ] Implement the webhook receiver as a heads-up trigger only, never a direct write.
- [ ] Write the edited-submission reconciliation test from `22_TESTING_STRATEGY.md`.
- [ ] Confirm the Kobo redirect URL is generated correctly with all hidden fields
      (`06_API_ARCHITECTURE.md`).

## Phase 4 — QA engine

- [ ] Implement `qa` app: `QARuleThreshold` (seeded from `15_QA_AND_DATA_QUALITY.md`
      defaults, pending PI confirmation), `QAEvent`.
- [ ] Implement hard-stop vs. soft-flag evaluation logic.
- [ ] Implement the QA queue API and human decision-recording flow.
- [ ] Unit test every threshold's hard-stop/soft-flag behaviour.

## Phase 5 — Respondent frontend flow

- [ ] Build R01–R10 per `07_FRONTEND_ARCHITECTURE.md` and `21_UI_UX_GUIDELINES.md`.
- [ ] Wire the eligibility referral path.
- [ ] Wire consent capture, including the separate KII-recording-consent flow.
- [ ] Wire the Kobo redirect handoff.
- [ ] Confirm no ABI score, band, or financing language appears anywhere in this flow
      (`AGENTS.md` ground rule 2/3, `18_DATA_PRIVACY_AND_COMPLIANCE.md`).

## Phase 6 — Research Operations Centre frontend

- [ ] Build A01–A12 per `07_FRONTEND_ARCHITECTURE.md`.
- [ ] Wire the six dashboards (`16_DASHBOARDS_AND_REPORTING.md`), confirming no
      identifying data leaks into any aggregate view.
- [ ] Wire the QA queue, reserve-activation flow, and audit log views.

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
