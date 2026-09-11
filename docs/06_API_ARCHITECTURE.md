# 06 — API architecture

Base path: `/api/v1/`. JSON only. Internal endpoints use JWT bearer tokens
(`Authorization: Bearer <token>`). Public respondent-facing endpoints (invitation
validation, eligibility, consent, participation choice) use the **invitation token**
itself as the access credential — no login — but must be rate-limited and must never
leak another Sample_ID's data. See `10_INVITATION_AND_CONSENT.md` for the token's
transport (a signed URL parameter, exchanged server-side for the hash lookup — the raw
token is never itself a bearer credential beyond that one exchange).

## Conventions

- Versioned from day one: `/api/v1/...`.
- List endpoints support pagination (`?page=`, `?page_size=`) and filtering via
  `django-filter` (e.g. `?province=Harare&status=S08`).
- Error format:
  ```json
  { "error": { "code": "string", "message": "human readable", "field_errors": {} } }
  ```
- OpenAPI schema auto-generated via `drf-spectacular` at `/api/schema/`, browsable docs
  at `/api/docs/`.
- Public respondent endpoints are rate-limited per token and per IP (DRF throttling) to
  blunt token-guessing/enumeration attempts.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/token/` | Obtain JWT (internal users) |
| POST | `/api/v1/auth/token/refresh/` | Refresh JWT |
| GET/POST | `/api/v1/sample-cases/` | List / import Main-400 & Reserve-400 (internal, `IsFieldCoordinatorOrAdmin`) |
| GET/PATCH | `/api/v1/sample-cases/{sample_id}/` | Retrieve / update one case, incl. workflow status |
| POST | `/api/v1/sample-cases/{sample_id}/activate-reserve/` | Activate a matched reserve (internal; requires `activation_reason`) |
| POST | `/api/v1/invitations/` | Issue a new invitation token for a `SampleCase` (internal) |
| GET | `/api/v1/invitations/validate/?t=<token>` | Public: validate a token, return minimal organisation-confirmation payload only |
| POST | `/api/v1/invitations/{token_id}/revoke/` | Revoke a token (internal) |
| POST | `/api/v1/eligibility/` | Public: submit the eligibility-gate answers for the current token |
| POST | `/api/v1/consent/` | Public: submit consent decision (participation or KII-recording) |
| GET | `/api/v1/kobo/redirect-url/` | Public: given a valid, consented token, return the tokenised Kobo launch URL with hidden fields populated |
| POST | `/api/v1/kobo/webhook/` | Kobo REST Services target — receives the new-submission heads-up (never trusted alone, see `11_KOBOTOOLBOX_INTEGRATION.md`) |
| POST | `/api/v1/kobo/reconcile/` | Manually trigger a reconciliation pull (internal; the scheduled job calls the same service function) |
| GET/POST | `/api/v1/contacts/{sample_id}/events/` | Contact-attempt log |
| GET/POST | `/api/v1/appointments/` | Appointment register |
| GET/POST | `/api/v1/kii/` | KII register |
| GET/POST | `/api/v1/documents/` | Documentary evidence corpus |
| GET/PATCH | `/api/v1/qa/queue/` | QA queue (submissions/KII/documents pending decision) |
| POST | `/api/v1/qa/{object_type}/{id}/decision/` | Record a QA decision |
| GET | `/api/v1/dashboards/executive/` | Executive dashboard aggregate (internal auth required) |
| GET | `/api/v1/dashboards/sampling/` | Sampling dashboard |
| GET | `/api/v1/dashboards/contact/` | Contact dashboard |
| GET | `/api/v1/dashboards/qa/` | QUAN QA dashboard |
| GET | `/api/v1/dashboards/kii-documents/` | KII/document dashboard |
| GET | `/api/v1/dashboards/cost/` | Cost dashboard |
| GET/POST | `/api/v1/costs/` | Cost events |
| GET | `/api/v1/export/analysis/` | De-identified analysis export (CSV; internal, `IsAnalystOrAdmin`) |
| GET | `/api/v1/export/operational/` | Full operational register export, contact data included (internal, `IsAdminOnly`) |
| GET | `/api/v1/audit/` | Audit log (internal, `IsAdminOnly`) |

## Key payload shapes

### `GET /api/v1/invitations/validate/?t=<token>`
```json
{
  "status": "valid",
  "organisation_name_confirmation": "Please confirm: is this Maundurahuku Farming Trust?",
  "requires_eligibility_check": true
}
```
Deliberately omits Sample_ID, stratum, Main/Reserve status, and any prior contact
history — per the original blueprint's Section 5.2 principle and `AGENTS.md` ground
rule 6.

### `POST /api/v1/kobo/redirect-url/`
```json
{
  "kobo_form_url": "https://kf.kobotoolbox.org/x/abcdef12?d[master_id]=MID-2026-000418&d[sample_id]=SID-2026-000418&d[invitation_wave]=2&d[administration_mode]=01&d[respondent_role_category]=CEO_MD&d[consent_status]=GIVEN&d[consent_version]=v1.2&d[portal_token_id]=b4f1...&d[ra_id]=",
  "administration_mode": "01"
}
```

### `GET /api/v1/dashboards/qa/`
```json
{
  "submissions_today": 6,
  "submissions_cumulative": 214,
  "consent_and_sample_id_completeness_percent": 99.5,
  "duplicate_ids_flagged": 0,
  "missingness_and_logic_failures": 3,
  "unusual_duration_flags": 2,
  "mode_distribution": { "01": 140, "02": 40, "03": 20, "04": 8, "05": 4, "06": 2 },
  "qa_queue_open": 5,
  "qa_median_turnaround_hours": 6.4
}
```

## Security

- Internal endpoints require an internal `Role`; dashboard/export endpoints additionally
  check the role/access matrix in `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- Public endpoints (`invitations/validate`, `eligibility`, `consent`, `kobo/redirect-url`)
  scope every read/write to the single `SampleCase` resolved from the token, never
  listing or exposing any other case.
- The `kobo/webhook/` endpoint validates Kobo's shared-secret header and is treated only
  as a trigger to run reconciliation early — its payload is never written directly to
  `QUANSubmission` without a corroborating API pull, per `11_KOBOTOOLBOX_INTEGRATION.md`.
- CORS restricted to `research.agribizframework.com` (and `localhost:3000` in dev) — see
  `24_ENVIRONMENT_CONFIGURATION.md`.
