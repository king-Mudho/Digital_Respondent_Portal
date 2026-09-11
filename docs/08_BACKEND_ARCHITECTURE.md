# 08 — Backend architecture

Django + Django REST Framework. Each service in `03_SYSTEM_ARCHITECTURE.md`'s component
diagram is a Django app inside the single `backend/` project — not a separate service.

## Directory structure

```
backend/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── celery.py           # Celery app + Beat schedule (reconciliation, reminders)
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/            # User, Role, JWT auth
│   ├── sampling/            # Organisation, StratumDefinition, SampleCase, reserve-lock logic
│   ├── contacts/            # Respondent, ContactEvent, Appointment
│   ├── consent/             # ConsentRecord
│   ├── invitations/         # InvitationToken issue/validate/revoke — see 10_INVITATION_AND_CONSENT.md
│   ├── kobo/                # QUANSubmission, ReconciliationLog, Kobo API client, webhook receiver
│   ├── messaging/           # MessageTemplate, MessageLog, WhatsApp Business Platform client
│   ├── kii/                 # KIIRecord
│   ├── evidence/            # DocumentRecord
│   ├── qa/                  # QARuleThreshold, QAEvent, QA decision logic
│   ├── dashboards/          # Read-only aggregate query endpoints for all six dashboards
│   ├── costs/                # CostEvent
│   └── audit/                # AuditEvent + signal handlers
├── api/
│   ├── urls.py              # Mounts each app's viewset routes under /api/v1/
│   └── permissions.py       # Role-based permission classes
├── tests/
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env.example
└── README.md
```

## Settings split

`base.py` holds shared settings (installed apps, DRF config, JWT config, CORS, Celery
broker). `dev.py` enables debug, permissive CORS, console email/WhatsApp-sandbox
backend. `prod.py` enforces `DEBUG=False`, `ALLOWED_HOSTS` from env, secure cookies,
HTTPS redirect. Select via `DJANGO_SETTINGS_MODULE` — see
`24_ENVIRONMENT_CONFIGURATION.md`.

## App responsibility notes

- `sampling` owns the Main-400/Reserve-400 integrity rule (`AGENTS.md` ground rule 4):
  every invitation-issuing code path must call through `sampling.services.is_invitable()`
  rather than checking `SampleCase.status` inline elsewhere, so the lock is enforced in
  exactly one place.
- `invitations` owns token generation, hashing, expiry and revocation
  (`10_INVITATION_AND_CONSENT.md`) — a pure, independently unit-testable module, since
  its correctness is the entire access-control boundary for the public respondent flow.
- `kobo` owns the scheduled reconciliation Celery task and the webhook receiver. The
  webhook handler never writes `QUANSubmission` rows directly — it only enqueues an
  early reconciliation run for that submission's asset, since Kobo's webhook does not
  fire on edits and cannot be treated as authoritative — see
  `11_KOBOTOOLBOX_INTEGRATION.md`.
- `qa` reads `QARuleThreshold` rows (config-driven per `AGENTS.md` ground rule 7) rather
  than hardcoding thresholds in Python — keep the *threshold values* in the database and
  the *evaluation logic* in Python, exactly as ABI keeps recommendation *text* in the
  database and *selection logic* in Python.
- `dashboards` is read-only: it composes queries across `sampling`, `contacts`, `kobo`,
  `kii`, `evidence`, `qa` and `costs` and must never expose `Organisation.name`,
  `Respondent.full_name`, or unbanded amounts on any aggregate response — see
  `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- `messaging` enforces the approved contact-attempt sequence (Day 0/2/4–5/7, see
  `12_CONTACT_CRM_AND_MESSAGING.md`) by only ever dispatching from a queue a human or the
  Celery Beat schedule populates — it never sends ad hoc, code-triggered messages outside
  that queue.

## Permissions

Define DRF permission classes in `api/permissions.py`:
- `IsFieldCoordinatorOrAdmin` — sample import, invitation issuance, reserve activation.
- `IsQAOrAdmin` — QA queue read/write.
- `IsAnalystOrAdmin` — de-identified export, dashboard reads.
- `IsAdminOnly` — operational export (contact data included), audit log, framework/role
  management.
- Public respondent endpoints use `AllowAny` but every query is scoped to the single
  `SampleCase` resolved from the validated invitation token — never a list endpoint for
  anonymous callers.

## Serializer convention

One serializer per model for internal/admin CRUD, plus purpose-built "read" serializers
for the six dashboard payloads (`06_API_ARCHITECTURE.md`) that aggregate across several
models and should not be forced through a single model serializer — same convention as
ABI's `08_BACKEND_ARCHITECTURE.md`.
