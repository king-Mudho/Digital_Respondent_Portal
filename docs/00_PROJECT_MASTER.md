# 00 — Project master

## Identity

**Name:** ABF-FST Digital Respondent Portal (respondent-facing module of the umbrella
**ABF-FST Digital Research & Bankability Platform**).

**Sponsor:** GigaFood Africa (development sponsor, as with the sibling ABI project).

**Principal Researcher:** Happyson Saina, Doctor of Strategic Management candidate,
Chinhoyi University of Technology.

**PI contact details** (for respondent-facing consent materials and invitation
messages — `18_DATA_PRIVACY_AND_COMPLIANCE.md`, `29_RESPONDENT_GUIDE_AND_MESSAGING.md`):
Phone `0773943709`, email `abffst.research.cut@gmail.com`.

**Ethics clearance:** Chinhoyi University of Technology Research Ethics Clearance
Letter, Annex 19, Form GRSD 17 SEBS/06/2025, approved 24.08.2026.

**Supervisors:** Dr L. Chikazhe, Dr J. Kanyepe.

**Study:** *Developing and Validating the Agribusiness Bankability Framework for Food
Systems Transformation through Novel Financing Models in Zimbabwe* (ABF-FST).

## Purpose

A low-cost, secure, invitation-controlled digital platform for the study's QUAN, KII and
documentary-evidence field operations. It authenticates selected respondents, captures
consent, routes participation, manages contacts and appointments, reconciles
KoboToolbox submissions, runs KII and document workflows, performs QA, and gives the
research team live fieldwork dashboards. It is a research-operations tool, not a
questionnaire engine (KoboToolbox remains that) and not a bankability-scoring tool (the
ABI engine is a separate, later module — see `25_FUTURE_ABI_ENGINE_PHASE4.md`).

## Fieldwork targets

- 400 usable QUAN responses (Main-400 sample; Reserve-400 held locked).
- 60 KIIs, or a justified information-power endpoint.
- 50–75 documentary records.
- Data lock: **30 November 2026**.

## Relationship to the ABI project

`agribusiness-bankability/` (this repository's sibling) is a **separate application**
implementing the Agribusiness Bankability Index self-assessment and public demo. The two
projects share a technology stack (Next.js/TypeScript + Django/PostgreSQL — see
`04_TECH_STACK.md`) and, in production, share hosting infrastructure under the
`agribizframework.com` domain, but they are **not the same codebase and are not
cross-linked in the UI**. See `20_EMBEDDING_WITH_ABI.md` for the full rationale: the
live ABI demo already shows provisional 0–100 scores to the public, which must never be
visible to a Main-400 respondent during primary data collection (per this study's own
`02_PRODUCT_REQUIREMENTS.md` and the original blueprint's Section 5.6/17.3).

## Design principles (carried from the v1.0 blueprint, unchanged)

- Portal controls identity, consent, routing and workflow; KoboToolbox remains the
  primary QUAN capture engine.
- The Main-400 remains the inferential sample; Reserve-400 stays locked until approved
  activation.
- Build only the minimum viable research-operations platform before data lock; defer the
  validated ABI scoring engine to Phase 4.

## Glossary

| Term | Meaning |
|---|---|
| Main-400 | The primary, inferentially-sampled 400 organisations. |
| Reserve-400 | A locked replacement pool, activated only for an authorised reason. |
| Master_ID | Permanent identifier for an organisation, independent of sampling status. |
| Sample_ID | Identifier for one organisation's inclusion in this study's sample — see `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`. |
| QUAN | The quantitative questionnaire, administered via KoboToolbox. |
| KII | Key informant interview. |
| RA | Research assistant. |
| PI | Principal Investigator (Happyson Saina). |
| Data lock | The point after which no further QUAN/KII/document records are accepted into the analytical dataset. |
| ABI | Agribusiness Bankability Index — the separate, later scoring module; see `25_FUTURE_ABI_ENGINE_PHASE4.md`. |

## Scope of this documentation set

This is the v1.0 **planning** documentation for the Digital Respondent Portal. It
supersedes, and closes the gaps identified in, `ABFFST_Digital_Portal_Review_and_
Development_Plan.docx` (GigaFood Africa QC review, September 2026) and reflects the
confirmed Next.js/TypeScript + Django/PostgreSQL stack. See `26_MVP_PHASING_AND_
ROADMAP.md` for phasing and `27_AGENT_EXECUTION_PLAN.md` for the build task list — neither
is to be executed until the PI approves per `AGENTS.md` ground rule 1.
