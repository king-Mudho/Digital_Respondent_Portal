# 18 — Data privacy, disclaimers & compliance

Financial and identifying information is being collected from real enterprises and
individuals for an active study. This document closes the most severe gap in the
September 2026 QC review: Zimbabwe's data-protection licensing requirement was not
addressed anywhere in the v1.0 blueprint.

## Zimbabwe Cyber and Data Protection Act (2021) — POTRAZ position

**This is a compliance precondition for going live, not an engineering task, and it is
CRITICAL priority.**

Zimbabwe's Cyber and Data Protection Act (2021) requires a data controller processing
personal data of **50 or more individuals** to hold a current data-controller licence
from **POTRAZ** (the Postal and Telecommunications Regulatory Authority of Zimbabwe,
Zimbabwe's data-protection authority), and — depending on the volume and sensitivity of
processing — to appoint a **Data Protection Officer** (DPO) with recognised credentials
(a certification pathway exists via the Harare Institute of Technology), notified to
POTRAZ. Non-compliance carries penalties reported up to a USD 1,000 fine or up to seven
years' imprisonment.

The Main-400 quantitative sample alone exceeds the 50-person threshold before KII
participants and gatekeeper contacts are even counted, and this portal will hold names,
roles, phone numbers and email addresses for all of them.

**Required action before Phase 0 closes** (tracked as a Phase 0 item in
`27_AGENT_EXECUTION_PLAN.md`, owned by the PI and CUT's legal/ethics office, not by the
development team):

1. Confirm in writing whether Chinhoyi University of Technology's existing institutional
   POTRAZ registration covers this study, or whether a separate/linked study-level
   registration is required.
2. Confirm whether a Data Protection Officer must be named specifically for this
   project, and if so, who.
3. Feed the answer directly into this document's access-control design (below) and into
   the hosting/data-residency decision in `23_DEPLOYMENT_ARCHITECTURE.md`, since
   licensing status may constrain where the database can legally be hosted.
4. Do not issue the first live Main-400 invitation until this is resolved — it is item
   0 of the go-live acceptance checklist in `28_DEFINITION_OF_DONE.md`.

This document records the open question, not the answer — the answer is a PI/legal
determination outside engineering scope.

## Required disclaimer text (use verbatim, do not paraphrase)

Shown on the consent step, the completion page, and any export:

> **Research study**: This portal supports data collection for a doctoral research
> study on agribusiness financing readiness. Your participation and responses are used
> for research purposes only. No score, rating, or financing decision is generated or
> shown to you as part of this process.

## Consent

- Explicit opt-in action before any data is persisted beyond a local, unsynced form
  state (`10_INVITATION_AND_CONSENT.md`).
- `ConsentRecord.decision` + `timestamp` recorded for every consent event, including
  withdrawal.
- Consent text explains what is collected, that it is for research purposes, and who to
  contact with questions (PI contact details, from `00_PROJECT_MASTER.md`).

## Anonymisation

- Aggregate/dashboard views never expose `Organisation.name` or `Respondent.full_name` —
  see the integrity rule in `05_DATABASE_ARCHITECTURE.md`.
- The de-identified analysis export (`16_DASHBOARDS_AND_REPORTING.md`) excludes all
  contact-identifying fields entirely, not just masks them.
- An individual organisation's own case detail (`A04`, internal only) may show its own
  identifying data — privacy rules govern *other* records' visibility, not an
  authorised internal user's visibility into the record they are working.

## Access control matrix

| Role | Own-case detail | Other cases (contact data) | Aggregate dashboards | De-identified export | Framework/threshold config |
|---|---|---|---|---|---|
| Public respondent | Own, via valid token only | No | No | No | No |
| Contact RA | Assigned cases | No | No | No | No |
| QUAN/Kobo QA RA | QA-relevant fields, assigned cases | No | QA dashboard only | No | No |
| KII RA | Assigned KII records | No | KII/document dashboard only | No | No |
| Documentary RA | Assigned document records | No | KII/document dashboard only | No | No |
| Analyst | No | No | Yes | Yes | No |
| Field Coordinator | Yes (all) | Yes (all) | Yes | No | No |
| PI / Admin | Yes (all) | Yes (all) | Yes | Yes | Yes |
| Supervisor | Read-only, all | Read-only, all | Yes | No | No |

**Implementation note (Sep 2026 hardening pass)**: `CONTACT_RA` had previously not been
included in *any* permission class at all, so every internal endpoint returned 403
regardless of case assignment. `SUPERVISOR_READONLY` was similarly corrected: it previously
had no read access to sample cases/contacts/KII/documents/QA (missing "Read-only, all"),
and was incorrectly included in the de-identified export's permission class (this table's
own "No" for that cell) via a permission class shared with the dashboards. See
`api/permissions.py` for the corrected `CanViewSampleCases`, `CanManageContact` and
`CanExportDeidentified` classes.

**Update (Sep 2026, case-assignment gap closed)**: Contact RA's "assigned cases" grant is
now literal, not "all cases" — `SampleCase.assigned_ra` (nullable FK to `accounts.User`,
Field Coordinator/Admin-writable) records which Contact RA a case belongs to, and every
Contact RA read/write across sampling, contacts, and invitations views is scoped to
`assigned_ra=request.user`. A case assigned to someone else, or not yet assigned, 404s
rather than 403s so its existence isn't leaked. Assignment is set from the sample case
detail page's "Assigned Contact RA" panel in the Research Operations Centre frontend.

## Data protection basics

- HTTPS everywhere in deployment (`23_DEPLOYMENT_ARCHITECTURE.md`).
- Secrets (DB credentials, JWT signing key, Kobo API token, WhatsApp API credentials)
  only via environment variables, never committed — see `24_ENVIRONMENT_CONFIGURATION.md`.
- `AuditEvent` records every sensitive action: invitation issuance/revocation, consent
  change, QA decision, reserve activation, data lock.
- Role-based permissions enforced server-side on every internal endpoint (never rely on
  the frontend hiding a button as the only protection).
- Recordings and documents live in a secure, access-controlled file store — never a
  generic cloud share link (`13_KII_MODULE.md`).
- Do not send sensitive respondent data to unapproved AI/third-party services — the six
  agents in `17_AI_FIELD_COORDINATOR.md` operate on this application's own infrastructure.
- Retention, withdrawal and destruction procedures follow the approved ethics protocol;
  a withdrawal (`10_INVITATION_AND_CONSENT.md`) triggers removal of identifying contact
  data while preserving the de-identified analytical record only where the ethics
  protocol permits.

## Language rules (repeat of `AGENTS.md` ground rule 2)

Never use "approved", "loan approval", "credit rating", "bankability score" or
"guarantee" in respondent-facing product copy. This is a research data-collection
instrument, not a financing product.
