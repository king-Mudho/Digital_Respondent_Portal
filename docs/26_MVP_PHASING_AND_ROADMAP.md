# 26 — MVP phasing & roadmap

## MVP scope

### Must-have before digital launch (Phase 1)

- Import Main-400 and locked Reserve-400, with the frozen identifier scheme
  (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`).
- Researcher login and role-based access.
- Invitation token generation and validation (`10_INVITATION_AND_CONSENT.md`).
- Mobile participant-information and consent pages.
- Eligibility gate and respondent-referral path.
- Kobo launch with controlled Sample_ID/Master_ID/mode fields
  (`11_KOBOTOOLBOX_INTEGRATION.md`).
- Contact and appointment register.
- Basic Main-400 status dashboard.
- Kobo submission reconciliation and QA status.
- Audit log and backup (against the RPO/RTO targets in `23_DEPLOYMENT_ARCHITECTURE.md`).

### Should-have during October (Phase 2)

- KII scheduling and transcript tracker.
- Documentary evidence repository.
- Automated reminder queues (`12_CONTACT_CRM_AND_MESSAGING.md`).
- Coverage dashboard and mode-effect monitoring.
- Cost/burn-rate dashboard.
- Physical-visit exception queue.

### Defer until after data lock (Phase 4)

- Public ABI self-assessment, automated bankability scoring, lender dashboards, credit
  recommendations, enterprise benchmarking, AI-generated financing advice — see
  `25_FUTURE_ABI_ENGINE_PHASE4.md`.
- Native Android/iOS application, unless a validated business need emerges.

## Roadmap

**Phase 0 — Governance and specification (immediate).** Freeze functional
requirements; resolve the POTRAZ/data-protection position
(`18_DATA_PRIVACY_AND_COMPLIANCE.md`); confirm ethics/supervisor position on electronic
consent, the Kobo integration, WhatsApp contact and remote recording; freeze the
identifier scheme (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`), field instruments, and the
Kobo integration contract (`11_KOBOTOOLBOX_INTEGRATION.md`); provision hosting, Kobo API
access, and WhatsApp Business Platform account + submit templates for Meta approval
(`12_CONTACT_CRM_AND_MESSAGING.md` — 3–5 business day lead time, start this immediately,
do not wait for Phase 1). **This phase also gates all build work per `AGENTS.md`
ground rule 1 — the PI must approve this documentation set and
`27_AGENT_EXECUTION_PLAN.md` before Phase 0 is considered closed.**

**Phase 1 — Research Operations MVP (September 2026).** Build invitation, eligibility,
consent, Kobo routing, Main-400 workflow, contact/appointment register, QA, basic
dashboard. Stand up dev/staging/production environments and CI
(`23_DEPLOYMENT_ARCHITECTURE.md`). Pilot internally and with authorised synthetic/test
records before live Main data.

**Phase 2 — Field Operations Expansion (October 2026).** Add KII/document modules, cost
dashboard, coverage analytics, reminder queues, physical-exception workflow.

**Phase 3 — Data-Lock Hardening (November 2026).** Reliability, reconciliation
robustness, backup/restore drill, audit exports, de-identification, final data-lock
controls. Freeze feature work in the final two weeks except security/critical fixes.

**Phase 4 — ABI Platform (post-validation).** Build the validated ABI scoring pipeline
as a data export into the sibling `agribusiness-bankability/` application, only after
the thesis measurement model and scoring rules are approved — see
`25_FUTURE_ABI_ENGINE_PHASE4.md`.

## Timeline discipline note

This roadmap inherits the same time pressure the September 2026 QC review flagged: the
Phase 1 "September 2026" target has very little runway remaining by the time this
documentation set is approved. `27_AGENT_EXECUTION_PLAN.md` Phase 0 explicitly includes
"developer/team assigned" as a same-week action item for exactly this reason.
