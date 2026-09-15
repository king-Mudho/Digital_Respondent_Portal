# Documentation index — ABF-FST Digital Respondent Portal v1.0

Read `AGENTS.md` at the repository root first. It defines the ground rules and the order
below is the required reading order for an implementing agent.

**Current state:** built, deployed and live at `research.agribizframework.com`
(Phases 0–10 of `27_AGENT_EXECUTION_PLAN.md` complete). The three approved registers are
loaded with real study data; no invitation has been issued and go-live remains the PI's
decision. This documentation set was written during the planning phase and is maintained
alongside the running system — where a document describes an intention and the code
disagrees, the code is what is deployed, and the discrepancy is a defect in one of them.
See `AGENTS.md` § Keeping the documentation honest.

| # | File | What it covers |
|---|------|-----------------|
| 00 | `00_PROJECT_MASTER.md` | Project identity, sponsor, stakeholders, glossary, scope, relationship to the sibling ABI project |
| 01 | `01_RESEARCH_CONTEXT.md` | Research purpose, Main-400/Reserve-400 design principle, fieldwork targets |
| 02 | `02_PRODUCT_REQUIREMENTS.md` | Functional & non-functional requirements, out-of-scope list |
| 03 | `03_SYSTEM_ARCHITECTURE.md` | High-level architecture, component diagram, repo layout, deployment topology |
| 04 | `04_TECH_STACK.md` | Frameworks, libraries, versions — Next.js/TypeScript + Django/PostgreSQL, matching ABI |
| 05 | `05_DATABASE_ARCHITECTURE.md` | Entities and field-level schema |
| 06 | `06_API_ARCHITECTURE.md` | REST endpoints, auth, conventions |
| 07 | `07_FRONTEND_ARCHITECTURE.md` | Next.js app structure, respondent + admin routes, offline behaviour |
| 08 | `08_BACKEND_ARCHITECTURE.md` | Django app structure, settings, permissions |
| 09 | `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` | Master_ID/Sample_ID specification, Main-400/Reserve-400 control, S00–S16 workflow engine |
| 10 | `10_INVITATION_AND_CONSENT.md` | Invitation token design, consent module, eligibility gate |
| 11 | `11_KOBOTOOLBOX_INTEGRATION.md` | Hidden fields, administration-mode codes, webhook limitation, reconciliation job |
| 12 | `12_CONTACT_CRM_AND_MESSAGING.md` | Contact/appointment register, WhatsApp Business Platform, reminder engine |
| 13 | `13_KII_MODULE.md` | Key informant interview scheduling, consent, transcript/coding workflow |
| 14 | `14_DOCUMENTARY_EVIDENCE_MODULE.md` | Document corpus, provenance, construct tagging |
| 15 | `15_QA_AND_DATA_QUALITY.md` | QA rule thresholds (numeric), QA queue, AI QA Agent scope |
| 16 | `16_DASHBOARDS_AND_REPORTING.md` | Executive, sampling, contact, QA, KII/document and cost dashboards |
| 17 | `17_AI_FIELD_COORDINATOR.md` | The six decision-support agents and human-approval boundaries |
| 18 | `18_DATA_PRIVACY_AND_COMPLIANCE.md` | Consent text, anonymisation, access control, Zimbabwe POTRAZ/Cyber and Data Protection Act position |
| 19 | `19_LANGUAGE_AND_ACCESSIBILITY.md` | Respondent-facing language decision, accessibility baseline |
| 20 | `20_EMBEDDING_WITH_ABI.md` | Subdomain/shared-infrastructure design with the ABI project, no-cross-link rule |
| 21 | `21_UI_UX_GUIDELINES.md` | Colour, type, legitimacy-first component patterns |
| 22 | `22_TESTING_STRATEGY.md` | Unit, API, component, E2E test plan |
| 23 | `23_DEPLOYMENT_ARCHITECTURE.md` | Nginx, HTTPS, environments, CI, process management, backups, RPO/RTO |
| 24 | `24_ENVIRONMENT_CONFIGURATION.md` | `.env` variables for frontend and backend |
| 25 | `25_FUTURE_ABI_ENGINE_PHASE4.md` | Post-validation ABI module — explicitly deferred |
| 26 | `26_MVP_PHASING_AND_ROADMAP.md` | Phase 0–4 roadmap against the 30 November 2026 data-lock date |
| 27 | `27_AGENT_EXECUTION_PLAN.md` | Phased, checkable build task list |
| 28 | `28_DEFINITION_OF_DONE.md` | Acceptance criteria, including the 15-item go-live checklist |
| 29 | `29_RESPONDENT_GUIDE_AND_MESSAGING.md` | Plain-language respondent walkthrough and ready-to-send invitation message templates |
| 30 | `30_PROIT_MODULE.md` | Pre-interview background research/verification tool (PROIT) — provenance rules, three-value architecture, and the record of the PI's risk-acceptance decision to enable it for respondents |
| 31 | `31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md` | Review-and-sign-off pack for the two items still running on engineering defaults: the QUAN QA rule thresholds and the Participant Information Sheet wording. **Awaiting sign-off** |
| 32 | `32_RESEARCHOS_BRIEF_GAP_ANALYSIS.md` | The ResearchOS engineering brief (13 Sep 2026) mapped item by item onto what is actually deployed — Built / Partial / Absent, with the five P0-level gaps and the two architectural decisions |
| 33 | `33_GO_LIVE_READINESS.md` | 14 Sep 2026 end-to-end audit: what was verified on production, the defects it found and fixed, and the ten things that must happen before the first live invitation, with owners |

## Not in the numbered set

| Where | What it covers |
|---|---|
| `../README.md` | The technical picture of the system as built: architecture, quick start, environment variables, tests, deployment, and the Notable fixes record |
| `../AGENTS.md` | Ground rules, the traps that have cost time in this codebase, and which documents to keep in step when behaviour changes |
| `tools/build_guide.py` | Builds the end-user guide PDF for the research team — sign-in, per-role screens, the respondent's experience, walkthrough, troubleshooting. The script is the source of truth; the PDF it writes is gitignored |
| `../backend/api/navigation.py` | Not documentation, but the single source of truth for which of the eight roles sees which screens |

## Reading order for humans

Start with `00`, `01`, `02` for context, then `09`–`12` for the operational core
(identifiers, tokens, Kobo, contact), then `18` for the compliance position, then `26` for
the roadmap.

Joining the research team rather than the codebase? Read the user manuals in
`manuals/` instead. They cover everything without the architecture:

- the **System Manual**;
- your **Role Guide** (one per role);
- the **Respondent Guide**, to share with respondents.

Each comes as Word and PDF, and `tools/build_manuals.js` builds them.

## Reading order for the agent

Full sequential order above, then `../README.md` for how the system was actually built,
and `27_AGENT_EXECUTION_PLAN.md` for the phase-by-phase record and the remaining open
questions. Phases 0–10 are complete, so most work now is maintenance against a live
system holding real data — `AGENTS.md` ground rule 1 sets out what that requires.
