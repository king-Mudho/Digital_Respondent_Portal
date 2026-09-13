# 16 — Dashboards & reporting

All dashboards are read-only aggregate views (`dashboards` app, `06_API_ARCHITECTURE.md`)
that never expose `Organisation.name`, `Respondent.full_name`, or unbanded financial
figures — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`. That invariant is enforced by a
parametrised test across all six
(`tests/test_dashboards.py::test_dashboards_never_expose_identifying_fields`).

> **Specification vs. as built.** Each section below states the full intended dashboard
> first, then an **As built** note giving the endpoint, its permission class, the exact
> response keys, and anything specified here that is *not* implemented. The two diverge in
> several places. Read the As-built note as the description of what exists today; treat the
> specification above it as the target, not a claim.

| Screen | Endpoint | Permission | Roles that see the nav entry |
|---|---|---|---|
| Executive | `GET /api/v1/dashboards/executive/` | `IsAnalystOrAdmin` | PI, Field Coordinator, Analyst, Supervisor |
| Sampling | `GET /api/v1/dashboards/sampling/` | `IsAnalystOrAdmin` | PI, Field Coordinator, Analyst, Supervisor |
| Contact | `GET /api/v1/dashboards/contact/` | `IsAnalystOrAdmin` | PI, Field Coordinator, Analyst, Supervisor |
| QUAN QA | `GET /api/v1/dashboards/qa/` | `IsQAOrAdmin` | PI, Field Coordinator, QUAN QA RA, Supervisor |
| KII/document | `GET /api/v1/dashboards/kii-documents/` | `CanViewKIIDocumentDashboard` | PI, Field Coordinator, Analyst, Supervisor, KII RA, Documentary RA |
| Cost | `GET /api/v1/dashboards/cost/` | `IsAnalystOrAdmin` | PI, Field Coordinator, Analyst, Supervisor |

Which roles see which screen is defined in `backend/api/navigation.py`, not here — see
`18_DATA_PRIVACY_AND_COMPLIANCE.md` for the access matrix.

## Executive dashboard

QUAN completed versus 400 target; KII completed versus 60/endpoint; documents coded
versus 50–75 target; days remaining to 30 November data lock; current fieldwork
expenditure and projected cost to completion; highest-risk province/actor/size coverage
gaps.

**As built** (`/admin/dashboard`): `quan_completed`, `quan_target`, `kii_completed`,
`kii_target`, `documents_coded`, `documents_target_low`, `documents_target_high`,
`days_remaining_to_data_lock`, `fieldwork_expenditure_to_date`,
`highest_risk_coverage_gaps` (the five lowest-filled strata by province × actor family ×
size class). *Not implemented:* projected cost to completion. Note the targets are
completion targets, not the loaded register size — 90 KII records are loaded against a
target of 60 completed interviews, and 100 documents against a 50–75 coded corpus,
because the surplus is reserve depth for nonresponse.

*(Original wording said "province/actor/value-chain/size" coverage gaps. Value chain is
not a stratification dimension — see `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` and the
Phase 2 open question in `27_AGENT_EXECUTION_PLAN.md`.)*

## Sampling dashboard

Main-400 by province, actor family and size class; verified, invited, started, submitted
and QA-passed counts by stratum; reserve activation count and reasons; digital-exclusion
and nonresponse map.

**As built** (`/admin/dashboard/sampling`): `main_by_province`, `main_by_stratum`
(verified count and total per stratum), `reserve_activations_by_reason`. *Not
implemented:* the invited/started/submitted/QA-passed breakdown per stratum, and the
digital-exclusion/nonresponse map.

## Contact dashboard

Organisations verified; eligible respondents identified; invitations due/sent/opened;
reminders due; appointments today/next seven days; refusals, unreachable cases and
physical-visit candidates.

**As built** (`/admin/dashboard/contact`): `organisations_verified`,
`eligible_respondents_identified`, `invitations_sent`, `invitations_opened`,
`appointments_upcoming`, `refusals`, `unreachable_cases`. *Not implemented:* invitations
*due*, reminders due, the today/next-seven-days split (upcoming is a single count), and
physical-visit candidates.

Note that `invitations_sent` and `invitations_opened` mean "reached at least this stage",
not "currently at this status" — `InvitationToken.status` advances monotonically, so an
exact-status filter would never count a token that has moved on. See the `_SENT_OR_LATER`
comment in `apps/dashboards/views.py`.

## QUAN QA dashboard

Submissions today/cumulative; consent and Sample_ID completeness; duplicate IDs;
missingness and logic failures (against the thresholds in
`15_QA_AND_DATA_QUALITY.md`); unusually short/long completion duration; mode
distribution and RA-assisted/self-administered mix; QA queries and turnaround time.

**As built** (`/admin/dashboard/qa`): `submissions_today`, `submissions_cumulative`,
`mode_distribution`, `qa_queue_open`, `qa_events_recorded`. *Not implemented:* consent
and Sample_ID completeness, duplicate-ID detection, missingness and logic-failure
summaries, duration outliers, and QA turnaround time. The underlying QA rule evaluation
does exist (`15_QA_AND_DATA_QUALITY.md`, `apps/qa/`) — it is the dashboard *summary* of
it that is not built.

This screen did not exist in the UI at all until 2026-09-13: the endpoint had been in
place since Phase 6 with nothing consuming it and no nav link to it, so Phase 6's "all six
dashboards render" checklist item was in fact satisfied by five dashboards plus an
endpoint. Worth remembering when checking off a screen-level item.

## KII/document dashboard

KII quotas and completion by stakeholder group; appointments, recordings, transcripts
and coding status; document corpus by source type and ABF-FST construct; evidence gaps
requiring targeted collection.

**As built** (`/admin/dashboard/kii-documents`): `kii_completed`, `kii_target`,
`kii_by_status`, `kii_by_stakeholder_category`, `documents_by_type`,
`documents_by_qa_status`, `documents_target_low`, `documents_target_high`. *Not
implemented:* appointment/recording/transcript/coding progress rollups, the ABF-FST
construct breakdown, and evidence-gap identification.

This is a counts-only view. The individual KII and document records live in their
registers (`/admin/kii`, `/admin/documents`), which are restricted to the roles that work
them.

## Cost dashboard

RA allowance by production day; airtime/data spend; transport and accommodation spend;
messaging spend (WhatsApp outside-window charges, SMS fallback — see
`12_CONTACT_CRM_AND_MESSAGING.md`); cost per QA-passed QUAN; cost per completed KII;
cost per included documentary record; projected cost at current response rate; savings
attributable to remote completion versus physical deployment.

**As built** (`/admin/cost`): `total_cost`, `cost_by_category` (the category breakdown
covers RA allowance, airtime/data, transport, accommodation, hosting, messaging and
other), `cost_per_qa_passed_quan`, `cost_per_completed_kii`. *Not implemented:* per
production-day allowance, cost per included documentary record, projected cost at current
response rate, and the remote-versus-physical savings comparison.

The screen also carries the cost-entry form, so it is the one dashboard that writes.
Read-only roles (Analyst, Supervisor) see the figures without the form.

## Exports

- **De-identified analysis export** (`GET /api/v1/export/analysis/`, `IsAnalystOrAdmin`):
  CSV, contact identifiers excluded entirely — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- **Full operational export** (`GET /api/v1/export/operational/`, `IsAdminOnly`):
  includes contact data, for internal operations use only, never distributed externally.
  The `/admin/export` screen does not show this download to anyone but the PI/Admin.
