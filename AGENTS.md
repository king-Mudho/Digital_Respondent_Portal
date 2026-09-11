# AGENTS.md — ground rules for the ABF-FST Digital Respondent Portal

Read this file first, then `docs/INDEX.md` for the full reading order. This file governs
any agent (human or AI) that modifies this codebase.

## Non-negotiable ground rules

1. **No build work starts without Principal Researcher sign-off.** This repository is in
   a planning/documentation phase. Do not scaffold `frontend/` or `backend/`, do not run
   `django-admin startproject`, `create-next-app`, or any equivalent, until the PI has
   explicitly approved `docs/27_AGENT_EXECUTION_PLAN.md` in writing. If you are an agent
   reading this before that approval exists, stop and say so — do not infer approval from
   the documentation being complete.
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
   `AuditEvent` — see `docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md`.
5. **KoboToolbox stays the QUAN capture engine.** Never build a competing form/question
   renderer inside this portal for the 24-question ABI-adjacent QUAN instrument. This
   portal only issues the tokenised redirect and reconciles submission status — see
   `docs/11_KOBOTOOLBOX_INTEGRATION.md`, including the documented webhook-does-not-fire-
   on-edits constraint that shapes the reconciliation design.
6. **Consent and eligibility gate everything.** No questionnaire link, no KII scheduling
   action, and no data persistence beyond a local draft may occur before the relevant
   consent record exists (`docs/10_INVITATION_AND_CONSENT.md`) and, for QUAN, before the
   eligibility gate has passed (same doc).
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

## Reading order for the agent

Full sequential order in `docs/INDEX.md`, then execute `docs/27_AGENT_EXECUTION_PLAN.md`
phase by phase.

## Progress tracking

Check off tasks in `docs/27_AGENT_EXECUTION_PLAN.md` in place (`- [ ]` → `- [x]`) as they
are actually verified working — migrations run, tests pass, screen renders — never ahead
of that. Commit at the end of each phase: `phase(N): <short summary>`. Never delete or
renumber a checklist item; if a task turns out to be unnecessary, leave it checked with a
note rather than removing it, so the history stays legible to the PI.

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
