# AGENTS.md — ground rules for the ABF-FST Digital Respondent Portal

Read this file first, then `docs/INDEX.md` for the full reading order. This file governs
any agent (human or AI) that modifies this codebase.

## Non-negotiable ground rules

1. **This system is built, deployed, and holds real research data.** The PI approved the
   build on 2026-09-11 and Phases 0–10 of `docs/27_AGENT_EXECUTION_PLAN.md` are complete;
   it is live at `research.agribizframework.com`. The production database holds the three
   **real** approved registers — 400 Main and 400 Reserve sample cases across 800 named
   organisations, 90 KII records, 100 documentary-evidence records — identifying a real
   study's real participants.

   Treat production as a live research record, not a scratch environment:

   - Never run `seed_drp_dev`, any `import_*` command, or a fixture loader against it.
   - Verify behaviour against production **read-only**, or inside a transaction you roll
     back. Prefer exercising a rule at the service layer over real HTTP calls that write
     rows you then have to clean up.
   - If a check does write something, delete the operational rows and say so — but leave
     the `AuditEvent`s. Editing the audit trail to tidy away your own actions is the one
     thing that log exists to prevent. Record what happened in
     `docs/27_AGENT_EXECUTION_PLAN.md` instead.
   - Before deleting any `SampleCase`, `Organisation`, or respondent record, establish
     whether it came from the import (imported rows carry provenance in `metadata`;
     hand-made ones do not) and what depends on it. Say what you found before acting.

   Go-live (Phase 11 — issuing the first real invitations) remains explicitly the PI's
   decision, not an engineering one. No invitation has been issued yet.
2. **Never use "approved", "loan approval", "credit rating", "bankability score" or
   "guarantee" anywhere a respondent can see it.** This portal is a data-collection
   instrument for an unvalidated research framework, not a financing product. See
   `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md`.
3. **The ABI bankability score is never computed or shown inside this portal.** The
   scoring engine is a separate, sibling application (`agribusiness-bankability/`) and is
   explicitly Phase 4 / post-validation for this study — see
   `docs/25_FUTURE_ABI_ENGINE_PHASE4.md` and `docs/20_EMBEDDING_WITH_ABI.md`. Do not import,
   call, or embed the ABI scoring code from this repository, even for a demo.
4. **Main-400/Reserve-400 integrity is a database-enforced constraint, not a UI
   convention.** A `SampleCase` with `sample_type = RESERVE` and `status = LOCKED` must be
   unreachable by every invitation-issuing code path, not merely hidden by the frontend.
   Reserve activation always requires a recorded reason, an authorising user, and an
   `AuditEvent` — see `docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md`. Main↔Reserve pairing
   goes through `sampling.services.set_matched_case()`, which refuses the pairings that
   break the lock — above all one Reserve claimed by two Main cases, which would make a
   single activation appear to cover both.
5. **KoboToolbox stays the QUAN capture engine.** Never build a competing form/question
   renderer inside this portal for the 24-question ABI-adjacent QUAN instrument. This
   portal only issues the tokenised redirect and reconciles submission status — see
   `docs/11_KOBOTOOLBOX_INTEGRATION.md`, including the documented webhook-does-not-fire-
   on-edits constraint that shapes the reconciliation design.
6. **Consent and eligibility gate everything, in code.** No questionnaire link, no KII
   scheduling action, no appointment request, and no data persistence beyond a local draft
   may occur before the relevant consent record exists
   (`docs/10_INVITATION_AND_CONSENT.md`) and, for QUAN, before the eligibility gate has
   passed. The public endpoints are `AllowAny` with a valid token as their only
   credential, so **the frontend declining to route somewhere is not a control** — put the
   check at the single service-layer point every caller goes through:

   - `consent.services.has_given_consent()` and `contacts.services.has_passed_eligibility()`
     are those checks; call them rather than re-deriving the condition.
   - `kobo.services.build_redirect_url()` enforces both before issuing a questionnaire URL.

   A docstring or a doc asserting a gate is not the gate. Both of these were claimed as
   enforced while only consent was actually checked, and the test that looked like it
   covered eligibility passed only because it never gave consent. When you write a test
   for a gate, prove it **refuses** — and check it still fails when you remove the gate.
7. **The methodology-adjacent numbers — QA thresholds, token expiry, reminder cadence,
   RPO/RTO targets — are data/config, not hardcoded literals**, exactly as ABI treats its
   `FrameworkVersion`. See `docs/15_QA_AND_DATA_QUALITY.md`,
   `docs/10_INVITATION_AND_CONSENT.md`, and `docs/23_DEPLOYMENT_ARCHITECTURE.md`. This lets
   the PI tune a threshold without a redeploy and keeps every change auditable.
8. **Repository layout is exactly two application folders**: `frontend/` and `backend/`
   at the top level, matching the sibling ABI repository's convention — no `mobile/`, no
   separate KII/document microservice, no standalone admin project. The AI Field
   Coordinator agents in `docs/17_AI_FIELD_COORDINATOR.md` are Django apps/services inside
   the one `backend/`, not separate deployables.
9. **Production domain is `research.agribizframework.com`**, read from environment
   configuration everywhere, never hardcoded — see `docs/24_ENVIRONMENT_CONFIGURATION.md`
   and `docs/20_EMBEDDING_WITH_ABI.md` for why it is a subdomain of the ABI production host
   with no navigational cross-links to the public ABI demo.
10. **`backend/api/navigation.py` is the only place role → screens is defined.** It is
    served to the frontend by `GET /api/v1/auth/me/`; the nav bar renders exactly what it
    returns, and each role lands on its own first screen. Never hardcode a screen list or
    a landing path in the frontend, and never add a screen to `SCREENS` without giving its
    endpoints a real DRF permission class — the navigation is UX only and is not a
    security boundary. Each of the eight roles is distinct: the three RA roles are not
    interchangeable, and a shared permission class across unrelated modules is how a KII
    RA ended up able to edit documentary evidence. `backend/tests/test_role_navigation.py`
    asserts every offered screen is reachable and every hidden one refused; keep it
    passing rather than adding exceptions to it.
11. **A role that cannot write must not be shown controls that write.** Read-only roles
    (Analyst, Supervisor) reach screens that mix reading and writing; gate the write half
    with `WriteOnly` / `ReadOnly` / `IfScreen` / `IfRole` from
    `frontend/components/admin/RoleGate.tsx`, rendered inside `AdminShell` so they can see
    the user context. This is courtesy, not protection — the permission class still is.

## Reading order for the agent

Full sequential order in `docs/INDEX.md`, then execute `docs/27_AGENT_EXECUTION_PLAN.md`
phase by phase.

## Traps in this codebase

Each of these has cost real time here. They are not hypothetical.

- **The shared E2E seed case accumulates state.** Consent and eligibility attach to the
  `SampleCase`, so by the second run `E2E_MAIN_SAMPLE_ID` already has GIVEN consent and
  eligible respondents on it. A spec asserting that a gate *refuses* something will
  silently pass without testing anything. Use `issueTokenOnFreshCase()` from
  `frontend/e2e/helpers.ts`, which builds its own organisation and case.
- **A test that cannot fail is worse than no test.** Two gate tests and an ordering test
  here were passing for the wrong reason. When a test guards a rule, delete the rule
  locally, watch the test go red, then put it back.
- **Silent failures in the respondent flow.** `try/finally` with no `catch` leaves a
  button re-enabled and the page unchanged, which a respondent alone with no support
  channel reads as a dead button. Every respondent-facing mutation surfaces an error via
  `frontend/lib/api/respondentErrors.ts`; keep it that way.
- **Unordered querysets under pagination.** `PageNumberPagination` over a queryset with no
  ordering makes page boundaries arbitrary — a row appears on two pages or none. If a
  model has no `Meta.ordering`, order the view's queryset explicitly.
- **Throttle scopes are shared unless you say otherwise.** Sign-in once shared the generic
  `anon` bucket with the public respondent endpoints, so a team behind one office NAT
  competed with respondent traffic and got "Invalid username or password" from a 429. Give
  a distinct concern its own scope.
- **Verify what you assert.** Numbers in `README.md` and the user guide are checked against
  the live system, not remembered. Cross-references in generated documents are checked by
  extracting them from the built artefact.

## Progress tracking

Check off tasks in `docs/27_AGENT_EXECUTION_PLAN.md` in place (`- [ ]` → `- [x]`) as they
are actually verified working — migrations run, tests pass, screen renders — never ahead
of that. Commit at the end of each phase: `phase(N): <short summary>`. Never delete or
renumber a checklist item; if a task turns out to be unnecessary, leave it checked with a
note rather than removing it, so the history stays legible to the PI.

Phases 0–10 are done, so most work now is maintenance rather than a phase. Use ordinary
conventional-commit prefixes (`feat:`, `fix:`, `docs:`) for that, and say in the message
what was actually wrong — a commit that fixes a defect nobody had noticed should explain
how it went unnoticed, not just what changed.

## Keeping the documentation honest

Four artefacts describe this system to people, and all four have been wrong at some point
while looking authoritative. When behaviour changes, check them:

- `README.md` — the technical picture, including the Notable fixes list.
- `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` — the access-control matrix and consent model;
  the place where a permission change has to land.
- `docs/tools/build_guide.py` — the end-user guide PDF for the research team. The script
  is the source of truth, the PDF is gitignored, and `REVISION` gets bumped whenever the
  content changes so a circulated copy can be told from an earlier one.
- `docs/27_AGENT_EXECUTION_PLAN.md` — the build record and open questions.

A doc that asserts a control exists, when the control does not, is worse than no doc: it
is what stopped anyone looking at the eligibility gate for months.

## Open questions convention

If you hit a genuine ambiguity the documentation doesn't resolve, do not guess silently.
Add it to the "Open questions" section at the top of `docs/27_AGENT_EXECUTION_PLAN.md`
with the assumption you made and why, exactly as the sibling ABI project's execution plan
does. Flag anything touching consent wording, sampling/reserve rules, QA thresholds, or
data-protection scope for explicit PI sign-off rather than resolving it yourself — these
are research and compliance decisions, not engineering ones.

## Definition of done

A phase is not complete until its items are checked in `docs/27_AGENT_EXECUTION_PLAN.md`
**and** the corresponding acceptance criteria in `docs/28_DEFINITION_OF_DONE.md` pass.
The 15-item go-live acceptance checklist there (reserve locks, consent gate, de-
identified export, role-based access, etc.) must pass in full before the first live
Main-400 invitation is issued — not before the first commit, before *go-live*.
