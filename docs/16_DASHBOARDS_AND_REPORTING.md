# 16 — Dashboards & reporting

All dashboards are read-only aggregate views (`dashboards` app, `06_API_ARCHITECTURE.md`)
that never expose `Organisation.name`, `Respondent.full_name`, or unbanded financial
figures — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.

## Executive dashboard

QUAN completed versus 400 target; KII completed versus 60/endpoint; documents coded
versus 50–75 target; days remaining to 30 November data lock; current fieldwork
expenditure and projected cost to completion; highest-risk province/actor/value-chain/
size coverage gaps.

## Sampling dashboard

Main-400 by province, actor family, value chain and size class; verified, invited,
started, submitted and QA-passed counts by stratum; reserve activation count and
reasons; digital-exclusion and nonresponse map.

## Contact dashboard

Organisations verified; eligible respondents identified; invitations due/sent/opened;
reminders due; appointments today/next seven days; refusals, unreachable cases and
physical-visit candidates.

## QUAN QA dashboard

Submissions today/cumulative; consent and Sample_ID completeness; duplicate IDs;
missingness and logic failures (against the thresholds in
`15_QA_AND_DATA_QUALITY.md`); unusually short/long completion duration; mode
distribution and RA-assisted/self-administered mix; QA queries and turnaround time.

## KII/document dashboard

KII quotas and completion by stakeholder group; appointments, recordings, transcripts
and coding status; document corpus by source type and ABF-FST construct; evidence gaps
requiring targeted collection.

## Cost dashboard

RA allowance by production day; airtime/data spend; transport and accommodation spend;
messaging spend (WhatsApp outside-window charges, SMS fallback — see
`12_CONTACT_CRM_AND_MESSAGING.md`); cost per QA-passed QUAN; cost per completed KII;
cost per included documentary record; projected cost at current response rate; savings
attributable to remote completion versus physical deployment.

## Exports

- **De-identified analysis export** (`GET /api/v1/export/analysis/`, `IsAnalystOrAdmin`):
  CSV, contact identifiers excluded entirely — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- **Full operational export** (`GET /api/v1/export/operational/`, `IsAdminOnly`):
  includes contact data, for internal operations use only, never distributed externally.
