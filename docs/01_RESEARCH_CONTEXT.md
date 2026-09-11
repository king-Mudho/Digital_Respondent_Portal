# 01 — Research context

## What this platform is — and is not

The Digital Respondent Portal is a **fieldwork-operations tool** for an active doctoral
study. It exists to reduce the cost and improve the auditability of national data
collection while preserving the approved sampling design — not to widen participation
beyond the approved sample, and not to make any financing or bankability determination.

It is **not** an open convenience survey: only selected Main-400 organisations may enter
the inferential QUAN workflow. It is **not** the questionnaire engine: KoboToolbox
remains the system of record for QUAN form logic and capture. It is **not** the ABI
scoring tool: see `25_FUTURE_ABI_ENGINE_PHASE4.md`.

## Why sample and identifier integrity must be system-enforced

Because the Main-400/Reserve-400 design is the basis for the study's inferential
validity, the platform must make it structurally impossible — not merely against
policy — for:

- a Reserve-400 organisation to receive an invitation while locked;
- a Reserve activation to occur without a recorded, authorised reason;
- an organisation's Master_ID/Sample_ID to be lost or duplicated across contact,
  consent, capture, QA and analysis.

This is implemented as system-level `SampleCase` state, not spreadsheet convention — see
`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`.

## Non-negotiable methodological requirements (from the approved field protocol)

- Only selected Main-400 organisations enter the inferential QUAN workflow.
- Every selected organisation retains its Master_ID and Sample_ID throughout contact,
  consent, data capture, QA and analysis.
- One knowledgeable organisational respondent is used unless a clearly separable
  enterprise unit is intentionally sampled.
- Respondent eligibility is confirmed before questionnaire administration.
- Electronic consent is captured and versioned; KII recording consent is captured
  separately.
- Administration mode is recorded for every response so mode effects can be assessed.
- Reserve-400 records remain system-locked until the corresponding Main case meets the
  approved replacement rule.
- QUAN, KII and documentary evidence remain distinct evidence streams, integrated
  analytically, not merged administratively.
- Contact identifiers are separated from de-identified analytical data wherever
  feasible.
- All actions affecting sampling, consent, response acceptance, reserve activation and
  data lock are auditable.

## Research validation / operational goals

- Authenticate and route exactly the approved sample, with a complete audit trail.
- Reduce the cost of national data collection versus a fully physical fieldwork model,
  by maximising web/telephone/WhatsApp completion.
- Reconcile every KoboToolbox submission against the portal's own invitation/consent/
  eligibility state before a record is treated as analysis-ready.
- Support the KII and documentary-evidence streams as auditable, provenance-tracked
  workflows, not ad hoc file collection.
- Give the PI and Field Coordinator a live view of coverage, QA backlog and burn rate
  against the 30 November 2026 data lock.

## Target respondents and users

Respondent-facing: an eligible knowledgeable organisational respondent (owner/founder,
CEO/MD, finance/credit/risk, operations, strategy, supply chain/commercial, or another
senior manager) at a selected Main-400 organisation, plus KII participants drawn from
the study's stakeholder categories.

Internal users: PI/System Admin, Field/Digital Coordinator, Contact RA, QUAN/Kobo QA RA,
KII RA, Documentary RA, Data Analyst — see `08_BACKEND_ARCHITECTURE.md` and
`18_DATA_PRIVACY_AND_COMPLIANCE.md` for the role/access matrix.
