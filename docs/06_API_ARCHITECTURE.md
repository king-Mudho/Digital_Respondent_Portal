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
- List endpoints paginate at 20 rows (`?page=`) and filter via `django-filter`
  (e.g. `?sample_type=MAIN&status=S08`). The registers also support DRF's `SearchFilter`
  via `?search=` — see the endpoint table for which fields each one matches.
- Error format:
  ```json
  { "error": { "code": "string", "message": "human readable", "field_errors": {} } }
  ```
  A DRF `ValidationError` has no top-level `detail`, so `api/exceptions.py` promotes the
  first field error into `message` rather than leaving the generic string — callers with
  no field-level UI (the whole respondent flow) show `message` alone.
- OpenAPI schema auto-generated via `drf-spectacular` at `/api/schema/`, browsable docs
  at `/api/docs/`. **The schema is generated from the code, so it is authoritative where
  this document and the code disagree.**
- Throttle scopes (`api/throttling.py`, rates in `config/settings/base.py`):
  `anon` 30/min per IP on public endpoints, `invitation_token` 20/min per token to blunt
  guessing of the manual entry code, and `login` (default 30/min, `LOGIN_THROTTLE_RATE`)
  on `/auth/token/` only. Sign-in has its own scope deliberately: sharing `anon` meant a
  team behind one office NAT competed with respondent traffic for the same allowance.

## Endpoints

55 endpoints as at 2026-09-13. Generate the current list with:

```bash
python manage.py show_urls 2>/dev/null || python -c "
import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup()
from django.urls import get_resolver
def w(r,p=''):
    for x in r.url_patterns:
        yield from (w(x, p+str(x.pattern)) if hasattr(x,'url_patterns') else [p+str(x.pattern)])
print('\n'.join(sorted(u for u in w(get_resolver()) if u.startswith('api/v1/'))))"
```

### Auth and session

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/auth/token/` | public (`login` throttle) | Obtain JWT (internal users) |
| POST | `/auth/token/refresh/` | public | Refresh JWT |
| GET | `/auth/me/` | authenticated | Who am I, my role, the screens my role may open, my landing path, and whether I am read-only. **The nav bar renders exactly this** — see `backend/api/navigation.py` |
| GET | `/auth/can-open/?path=` | authenticated | May this role open this admin path (including detail routes with no nav entry of their own) |
| POST | `/auth/change-password/` | authenticated | Change your own password; every role has this |
| GET | `/auth/contact-ras/` | `CanViewSampleCases` | Contact RA usernames, for the assignment dropdown |

### Sampling

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET/POST | `/sample-cases/` | `CanViewSampleCases` (POST: FC/Admin) | List / create. `?search=` matches sample_id, organisation name, Master ID. Contact RA's GET is scoped to its assigned cases |
| GET/PATCH | `/sample-cases/{sample_id}/` | `CanViewSampleCases` | Retrieve / update. Status fields are read-only here — use `/transition/`. `matched_case` routes through `set_matched_case()` |
| POST | `/sample-cases/{sample_id}/transition/` | `IsFieldCoordinatorOrAdmin` | The only sanctioned way to change `workflow_status` by hand; validates S00–S16 and audits. S05→S10 also advance automatically from respondent and QA events (`09`) |
| POST | `/sample-cases/bulk-transition/` | `IsFieldCoordinatorOrAdmin` | `{from_status, sample_ids?}` — move Main cases one verification step (S00→S01→S02→S03 only), each audited |
| POST | `/sample-cases/{sample_id}/withdraw/` | `IsFieldCoordinatorOrAdmin` | `{reason, method?}` — record a withdrawal: WITHDRAWN consent, invitations revoked, S12 where allowed, contact details erased. 409 if already withdrawn |
| POST | `/sample-cases/{sample_id}/activate-reserve/` | `IsFieldCoordinatorOrAdmin` | Activate a matched reserve; requires `activation_reason` |
| GET | `/sample-cases/{sample_id}/available-reserves/` | `IsFieldCoordinatorOrAdmin` | Reserves this Main case may be paired with (still LOCKED, unclaimed), same stratum first |
| GET/POST | `/organisations/` | `CanViewSampleCases` (POST: FC/Admin) | Register / list organisations. `?search=` matches name, Master ID, district |

### Invitations, eligibility and consent (public flow)

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET/POST | `/invitations/` | `CanManageContact` | List a case's invitation history / issue a new token. POST returns `token_id`, `raw_token`, `raw_manual_code`, `expires_at` — the only time the raw values are ever visible |
| GET | `/invitations/validate/?t=` | public | Validate a token; minimal organisation-confirmation payload only |
| POST | `/invitations/{token_id}/revoke/` | `CanManageContact` | Revoke a token |
| POST | `/eligibility/` | public | Submit the eligibility-gate answers for the current token |
| POST | `/consent/` | public | Submit a consent decision (participation or KII-recording) |

### Kobo

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/kobo/redirect-url/?t=` | public | The tokenised Kobo launch URL. Requires **both** a passed eligibility check and GIVEN consent. `portal_token_id` is `<token id>.<HMAC>`; also marks the token SURVEY_STARTED and the case S07 |
| POST | `/kobo/webhook/` | shared secret | New-submission heads-up; never trusted alone (`11_KOBOTOOLBOX_INTEGRATION.md`) |
| POST | `/kobo/reconcile/` | `IsQAOrAdmin` | Manually trigger a reconciliation pull |
| GET | `/kobo/reconciliation-status/` | `IsQAOrAdmin` | `{configured, last_run}` — whether the asset UID and API token are set, and the last run's timing, counts and error |
| GET | `/kobo/forms/` | signed in (403 if the role has no form) | Main-study forms this role may open, and `email_configured` |
| GET | `/kobo/forms/{key}/submissions/?page=` | per form: questionnaire → QA; kii → KII RA; documents → Documentary RA; plus FC, PI, Supervisor | Completed submissions from KoboToolbox, newest first |
| GET | `/kobo/forms/{key}/submissions/{id}/pdf/` | as above | The submission as a PDF (labels, sections, repeats); audited |
| POST | `/kobo/forms/{key}/submissions/{id}/email/` | as above, not Supervisor | `{recipient: me\|respondent}` — PDF to the user's own address, or (questionnaire) the respondent's address on file while consent stands. 503 if email isn't set up; audited with a masked address |

### Contact, appointments, QA

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET/POST | `/contacts/{sample_id}/events/` | `CanManageContact` | Contact-attempt log |
| GET/POST | `/contacts/{sample_id}/respondents/` | `CanManageContact` (Contact RA: assigned cases) | People at a case and their contact details; `is_eligible` records a staff screening (sets `eligibility_checked_by`). 409 after withdrawal. Audited with changed field names only |
| PATCH | `/contacts/respondents/{id}/` | `CanManageContact` (Contact RA: assigned cases) | Correct a person's details |
| GET/POST | `/appointments/` | `CanManageContact` (POST: public, token) | Appointment register. Public POST requires GIVEN consent and a future `scheduled_for` |
| POST | `/appointments/{id}/status/` | `CanManageContact` | Confirm / complete / miss / cancel |
| GET | `/follow-ups/` | `CanManageContact` (Contact RA: assigned cases) | Reminders due and not yet sent, with a `whatsapp_link` (wa.me) carrying the approved text |
| POST | `/follow-ups/mark-sent/` | `CanManageContact` | `{sample_id, template}` — record a reminder sent by hand, against the RA, audited |
| GET | `/qa/queue/` | `IsQAOrAdmin` | Submissions pending a human QA decision |
| POST | `/qa/submission/{id}/decision/` | `IsQAOrAdmin` | Record a QA decision; a note is mandatory |

### KII and documentary evidence

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET/POST | `/kii/` | `CanManageKII` | KII register. `?search=` matches KII ID, participant name/role, category, organisation |
| GET/PATCH | `/kii/{id}/` | `CanManageKII` | One KII record |
| POST | `/kii/{id}/status/` | `CanManageKII` | Status transition; completing with a recording requires recording consent |
| POST | `/kii/{id}/consent/` | `CanManageKII` | Record participation or recording consent, always as separate rows |
| POST | `/kii/{id}/transcript-status/` | `CanManageKII` | Advance transcript progress |
| POST | `/kii/{id}/coding-status/` | `CanManageKII` | Advance coding progress |
| GET/POST | `/documents/` | `CanManageDocuments` | Document corpus. `?search=` matches document ID, title, author, value chain |
| GET/PATCH | `/documents/{id}/` | `CanManageDocuments` | One document record |
| POST | `/documents/{id}/authenticity/` | `CanManageDocuments` | Record an authenticity assessment; always stores the reviewer |
| POST | `/documents/{id}/qa-status/` | `CanManageDocuments` | Include / exclude; refuses INCLUDED while authenticity is UNVERIFIED |

`CanManageKII` and `CanManageDocuments` are deliberately distinct classes. They were one
shared `IsQAOrAdmin` until 2026-09-13, which let a KII RA edit documentary evidence and a
Documentary RA take QUAN QA decisions.

### PROIT (`30_PROIT_MODULE.md`)

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/proit/field-catalog/` | internal | The field modules a pre-profile can cover |
| GET | `/proit/probe-templates/` | internal | Role-specific KII probe templates |
| GET/POST | `/proit/pre-profiles/` | internal | List / create pre-profiles |
| GET/PATCH | `/proit/pre-profiles/{id}/` | internal | One pre-profile |
| POST | `/proit/pre-profiles/{id}/lock/` | internal | Researcher review-and-lock, before the respondent is contacted |
| GET/POST | `/proit/pre-profiles/{id}/fields/` | internal | The per-field three-value records |
| POST | `/proit/fields/{field_id}/evidence/` | internal | Attach an evidence record (source, date, locator, confidence) |
| GET | `/proit/respondent-profile/?t=` | public | The locked pre-profile for this token, or null when there is nothing to verify |
| POST | `/proit/respondent-verify/` | public | The respondent's confirm / correct / decline for one field |

### Dashboards, costs, exports, audit

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/reports/overview/?range=7\|30\|90\|all` | `IsAnalystOrAdmin` | Reports screen: KPIs, case funnel (each case once, at its furthest stage), submissions per day, coverage by province/organisation type/size, workflow status, completion-time histogram, administration mode, QA outcomes and flag reasons, contact outcomes, KII/document progress. Counts and rates only; cached 60 s |
| GET | `/dashboards/executive/` | `IsAnalystOrAdmin` | Executive aggregate |
| GET | `/dashboards/sampling/` | `IsAnalystOrAdmin` | Sampling aggregate |
| GET | `/dashboards/contact/` | `IsAnalystOrAdmin` | Contact aggregate |
| GET | `/dashboards/qa/` | `IsQAOrAdmin` | QUAN QA aggregate |
| GET | `/dashboards/kii-documents/` | `CanViewKIIDocumentDashboard` | KII/document aggregate |
| GET | `/dashboards/cost/` | `IsAnalystOrAdmin` | Cost aggregate |
| GET/POST | `/costs/` | `IsAnalystOrAdmin` (POST: FC/Admin) | Cost events |
| GET | `/export/analysis/` | `IsAnalystOrAdmin` | De-identified analysis export (CSV) |
| GET | `/export/operational/` | `IsAdminOnly` | Full operational export, contact data included |
| GET | `/audit/` | `IsAdminOnly` | Audit log |

Exact response shapes per dashboard are in `16_DASHBOARDS_AND_REPORTING.md`, which also
records what each one specifies but does not yet implement.

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

### `GET /api/v1/kobo/redirect-url/?t=<token>`
```json
{
  "kobo_form_url": "https://ee.kobotoolbox.org/x/AbCd1234?d[master_id]=MID-HA-000418&d[sample_id]=SID-2026-000418&d[invitation_wave]=2&d[administration_mode]=01&d[respondent_role_category]=CEO_MD&d[consent_status]=GIVEN&d[consent_version]=v1.0&d[portal_token_id]=b4f1...&d[ra_id]=",
  "administration_mode": "01"
}
```
Refused with `403 consent_required` without GIVEN participation consent, and
`403 eligibility_required` without an eligible respondent recorded for the case. Both are
enforced in `apps.kobo.services.build_redirect_url()` — the single point every caller goes
through — because this endpoint is public and the frontend's routing is not a control.
After both gates, `503 questionnaire_unavailable` if `KOBO_FORM_URL` is not set; the base
of `kobo_form_url` is that setting verbatim, never built from the asset UID.

### `GET /api/v1/auth/me/`
```json
{
  "username": "contact_ra",
  "role": "CONTACT_RA",
  "role_label": "Contact RA",
  "screens": [
    { "id": "sample_register", "path": "/admin/sample", "label": "Main-400 Register" },
    { "id": "appointments", "path": "/admin/appointments", "label": "Appointments" }
  ],
  "landing_path": "/admin/sample",
  "read_only": false,
  "universal_paths": ["/admin/account"],
  "child_paths": { "/admin/sample/": "sample_register", "/admin/proit/": "sample_register" }
}
```
`universal_paths` and `child_paths` are sent so the frontend guard is generic and
server-driven — the path policy lives in `backend/api/navigation.py` only and cannot drift
into a second hardcoded copy in the UI.

### `GET /api/v1/dashboards/qa/`
```json
{
  "submissions_today": 6,
  "submissions_cumulative": 214,
  "mode_distribution": { "01": 140, "02": 40, "03": 20, "04": 8, "05": 4, "06": 2 },
  "qa_queue_open": 5,
  "qa_events_recorded": 209
}
```
*(An earlier version of this document showed `consent_and_sample_id_completeness_percent`,
`duplicate_ids_flagged`, `missingness_and_logic_failures`, `unusual_duration_flags` and
`qa_median_turnaround_hours` in this payload. None of those are implemented — the example
described the aspiration in `16_DASHBOARDS_AND_REPORTING.md`, not the endpoint. Corrected
2026-09-13.)*

## Security

- Internal endpoints require an internal `Role`; dashboard/export endpoints additionally
  check the role/access matrix in `18_DATA_PRIVACY_AND_COMPLIANCE.md`. Each of the eight
  roles is checked by a specific permission class — never "is logged in", and never one
  class shared across unrelated modules.
- **`GET /auth/me/` is not a security boundary.** It tells the frontend which screens to
  render so a user is not shown links that 403 on click. Every endpoint still enforces its
  own permission class, and a screen reached another way (a shared URL, an old bookmark)
  is refused by the API regardless.
- Public endpoints (`invitations/validate`, `eligibility`, `consent`, `kobo/redirect-url`,
  `proit/respondent-profile`, `proit/respondent-verify`, and `POST /appointments/`) scope
  every read/write to the single `SampleCase` resolved from the token, never listing or
  exposing any other case.
- **A public endpoint's only credential is a valid token**, so anything that must not
  happen without consent or eligibility has to check it server-side. The frontend
  declining to route somewhere is not a control: the eligibility gate was asserted in a
  docstring, in `16`/`28`, and in a test that passed for an unrelated reason, while the
  code checked only consent. See `apps.consent.services.has_given_consent` and
  `apps.contacts.services.has_passed_eligibility` — call those rather than re-deriving
  the condition.
- The `kobo/webhook/` endpoint validates Kobo's shared-secret header and is treated only
  as a trigger to run reconciliation early — its payload is never written directly to
  `QUANSubmission` without a corroborating API pull, per `11_KOBOTOOLBOX_INTEGRATION.md`.
- CORS restricted to `research.agribizframework.com` (and `localhost:3000` in dev) — see
  `24_ENVIRONMENT_CONFIGURATION.md`.
