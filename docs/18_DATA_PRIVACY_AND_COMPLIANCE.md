# 18 — Data privacy, disclaimers & compliance

Financial and identifying information is being collected from real enterprises and
individuals for an active study. This document closes the most severe gap in the
September 2026 QC review: Zimbabwe's data-protection licensing requirement was not
addressed anywhere in the v1.0 blueprint.

## Zimbabwe Cyber and Data Protection Act (2021) — POTRAZ position

Zimbabwe's Cyber and Data Protection Act (2021) requires a data controller processing
personal data of **50 or more individuals** to hold a current data-controller licence
from **POTRAZ** (the Postal and Telecommunications Regulatory Authority of Zimbabwe,
Zimbabwe's data-protection authority), and — depending on the volume and sensitivity of
processing — to appoint a **Data Protection Officer** (DPO) with recognised credentials
(a certification pathway exists via the Harare Institute of Technology), notified to
POTRAZ.

The Main-400 quantitative sample alone exceeds the 50-person threshold before KII
participants and gatekeeper contacts are even counted, and this portal will hold names,
roles, phone numbers and email addresses for all of them, so this question was not one
to leave unanswered.

**Resolved (2026-09-12).** Chinhoyi University of Technology's Research Ethics
Clearance Letter (Annex 19, Form GRSD 17 SEBS/06/2025, approved 24.08.2026, signed by
Dr. M. C. Mwando, Chairperson of the University Research Committee — Research Ethics)
grants permission to carry out this study as described in the approved proposal, under
University policies and guidelines. Per the PI's determination, this study operates
under Chinhoyi University of Technology's institutional research governance and
permission, which covers the data-protection position addressed above — no
separate/linked study-level POTRAZ registration or study-specific DPO appointment is
being pursued beyond that institutional coverage. This is a PI/university determination,
not an engineering one; the letter is held by the PI. This no longer blocks Phase 11
go-live in `27_AGENT_EXECUTION_PLAN.md` / `28_DEFINITION_OF_DONE.md`.

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

**Update (Sep 2026, navigation scoped to role)**: this matrix is now also what each role
*sees*, not only what it is allowed to reach. `backend/api/navigation.py` is the single
source of truth mapping role → screens, served by `GET /api/v1/auth/me/`; the nav bar
renders exactly that list and a screen outside it shows an explicit "not part of your
role" card. Each role also lands on its own first screen at sign-in — `/admin/dashboard`
was previously hardcoded for everyone though Contact, QUAN QA, KII and Documentary RAs
are all refused it.

Three permission errors this surfaced, now fixed: `IsQAOrAdmin` was shared by the QA, KII
and documentary endpoints, so a KII RA could edit document records and a Documentary RA
could take QUAN QA decisions (split into `IsQAOrAdmin` / `CanManageKII` /
`CanManageDocuments`); the KII/document dashboard used `IsAnalystOrAdmin`, excluding the
very KII and Documentary RAs this table grants it to (now `CanViewKIIDocumentDashboard`);
and `/api/v1/dashboards/qa/` had no frontend page at all, so the QUAN QA RA's own
dashboard did not exist. Per-role coverage is pinned by
`backend/tests/test_role_navigation.py` and `frontend/e2e/role-scoped-navigation.spec.ts`.

The nav remains UX only. Every endpoint still enforces its own permission class — see the
bullet below about never relying on a hidden button.

**Update (Sep 2026, eligibility gate actually enforced)**: `kobo.services.
build_redirect_url` documented itself as issuing no questionnaire URL "without a passed
eligibility check and GIVEN participation consent", and docs/28's Definition of Done says
an ineligible respondent is "never" routed to the questionnaire — but only the consent
half was implemented. `/api/v1/consent/` is `AllowAny` and takes a valid token as its only
credential, so anyone screened out by the eligibility page could POST consent directly and
be handed a Kobo URL; the frontend declining to route them there was not a control.
`build_redirect_url` now also requires `contacts.services.has_passed_eligibility`, and the
test that appeared to cover this (`test_ineligible_respondent_never_reaches_kobo_redirect`)
was passing only because it never gave consent — it now gives consent first, which is what
a bypass looks like. Because `record_eligibility_check` never overwrites a prior attempt,
a case screened through a gatekeeper first still proceeds once the right person is
identified. No invitations had been issued when this was fixed, so no live respondent was
affected.

**Update (Sep 2026, appointment requests are consent-gated — PI decision)**: the public
`POST /api/v1/appointments/` previously required only a valid token, so a respondent could
ask for a researcher call before consenting. The PI's decision is that it must not: an
appointment request is a researcher-assisted route into the same study, not a separate
lightweight enquiry — it records a named person's stated availability against an
identified organisation and places them on an RA's call list. Reaching that without having
agreed to take part would collect contact data outside consent. The endpoint now returns
`403 consent_required` unless `consent.services.has_given_consent` passes, matching the
gate already on the self-administered route. Declining consent is refused too, not just
the absence of a decision.

Note that consent attaches to the `SampleCase`, not to a token: a later invitation wave to
a case that already consented inherits that consent, which is the documented model.

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
