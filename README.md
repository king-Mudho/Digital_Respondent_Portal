# ABF-FST Digital Respondent Portal

A research-operations platform supporting *"Developing and Validating the Agribusiness
Bankability Framework for Food Systems Transformation through Novel Financing Models in
Zimbabwe"* (ABF-FST). Principal Researcher: Happyson Saina, Doctor of Strategic
Management candidate, Chinhoyi University of Technology (Supervisors: Dr L. Chikazhe,
Dr J. Kanyepe).

The portal authenticates and routes the study's selected Main-400 respondents (plus a
locked Reserve-400), captures consent and eligibility, launches the KoboToolbox
questionnaire with controlled identifiers, reconciles submissions, and runs the KII,
documentary-evidence, contact/CRM, QA and fieldwork-cost operations behind the 400 QUAN
/ 60 KII / 50–75 document data-collection target. It is **not** a public survey tool and
does **not** expose any ABI bankability score to respondents — see
`docs/00_PROJECT_MASTER.md` for full project identity and `docs/20_EMBEDDING_WITH_ABI.md`
for why it is deliberately kept separate from the public ABI self-assessment demo.

## Status

**Built and deployed** (Phases 0–10 of `docs/27_AGENT_EXECUTION_PLAN.md`), **live at
[research.agribizframework.com](https://research.agribizframework.com)**, pending
go-live (Phase 11 — issuing real Main-400 invitations, which is explicitly the PI's
decision, not an engineering one).

**The three approved registers are loaded** (Sep 2026): 400 Main and 400 Reserve sample
cases across 800 organisations with all 400 pairs wired, 90 KII records (Core-60 plus
Reserve-30), and 100 documentary-evidence records. No invitation has been issued and no
consent recorded — fieldwork itself has not started.

Two QA passes have run against this codebase, both by hand in a real browser as well as
by test:

- **First hardening pass** — every screen and endpoint exercised; several real defects
  fixed, most importantly a production routing bug that had silently broken every login
  and dashboard load for hours.
- **Second pass (role, register and respondent-flow audit)** — role-scoped navigation,
  the missing QA dashboard, register paging/search, and two access-control gaps that
  documentation claimed were closed but were not.

Both are itemised under [Notable fixes](#notable-fixes). Current state: **260 backend
tests** passing (`pytest`), **26 Playwright specs** (25 run, 1 intentionally skipped),
`ruff check`, `tsc --noEmit` and `eslint` all clean.

See `docs/27_AGENT_EXECUTION_PLAN.md` for the full phase-by-phase build record and
`docs/28_DEFINITION_OF_DONE.md` for what remains before the PI's own go-live decision:
WhatsApp Business Platform Meta template approval, a real KoboToolbox production
asset, and the full go-live checklist run against this deployment. The POTRAZ/data-
protection determination is resolved (`docs/18_DATA_PRIVACY_AND_COMPLIANCE.md`).

This is a research-operations tool supporting an active fieldwork study with a
30 November 2026 data-lock date — not a production lending or credit-decision system.
See `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` for the compliance position.

---

## How the portal works, step by step

The portal has two halves that share one Django backend: a **public, invitation-gated
respondent flow** (nobody can browse in — every visit starts from a personal link) and
an **internal Research Operations Centre** for the PI, admins, field coordinators and
analysts.

### 1. Sampling and identifiers (the foundation)

The Main-400/Reserve-400 registers were loaded by `manage.py import_quan_register` from
the approved sampling register. Organisations added afterwards are registered from
`/admin/organisations` in the Research Operations Centre, which also creates the sample
case and (from the case detail page) pairs it with its matched Reserve — Django admin is
not needed for any part of this.

**Organisations** are stratified by **province × actor family × size class**. Entity type
and value chain are recorded as free-text descriptive fields and are deliberately *not*
part of the stratum match — the schema originally assumed value chain was a stratum
dimension, which the real register contradicted. Each slot in the design has one **Main**
case and one locked **Reserve** case. Every organisation gets a system-generated
`Master_ID` (`MID-<province>-<sequence>`) and every sample case a `Sample_ID`
(`SID-<year>-<sequence>`), both assigned via a DB-sequence with row locking so two
concurrent requests can never collide — never user-entered, never reused.

A Main case's `Sample_ID` moves through a fixed **S00–S16 workflow status**, validated
by `apps.sampling.services.transition_workflow_status()` — nothing else in the codebase
is allowed to change it:

| Status | Meaning |
|---|---|
| S00 | Selected Main |
| S01 | Verification required |
| S02 | Organisation verified |
| S03 | Eligible respondent identified |
| S04 | Invitation prepared |
| S05 | Invitation sent |
| S06 | Invitation opened |
| S07 | Survey started |
| S08 | Survey submitted |
| S09 | QA query |
| S10 | QA passed |
| S11 | Completed |
| S12 | Refused |
| S13 | Nonresponse |
| S14 | Ineligible |
| S15 | Duplicate/inactive |
| S16 | Reserve eligible for activation |

S12–S15 are terminal "drop" states — a case that lands in one of them makes its matched
Reserve case eligible for **activation** (S16), which always requires one of five
documented reasons (ineligible, inactive, duplicate, refusal, nonresponse exhausted) plus
a human-written evidence note, and is written atomically with an audit-log entry. A
Reserve case can never be invited while `LOCKED` — this is enforced in the database
service layer, not just hidden in the UI.

### 2. The respondent-facing flow (`/i/<token>`, screens R01–R10)

An admin issues a personal invitation (32-byte random token, only its salted SHA-256
hash ever stored; a matching 8-character manual code exists for phone-assisted
administration). The respondent's link looks like
`https://research.agribizframework.com/i/<token>` and walks through:

1. **R02 Invitation validation** — the token is checked (not expired, not revoked, not
   superseded by a newer one issued to the same case).
2. **R03 Organisation confirmation** — respondent confirms they represent the named
   organisation.
3. **R04 Eligibility gate** — respondent selects their role from a fixed list (owner,
   CEO/MD, finance/credit/risk, operations, strategy/BD, supply chain/commercial, other
   senior manager). Anyone outside this list is routed to a referral message, never
   silently marked eligible.
4. **R05 Participant information** — the study information sheet.
5. **R06 Electronic consent** — participation consent, captured as its own
   `ConsentRecord` row.
6. **PROIT verification** (`/i/<token>/verify`) — if a locked pre-profile exists for the
   case, the respondent confirms, corrects, or declines each background fact the research
   team already gathered, instead of answering it from scratch. Self-skips entirely when
   there is nothing to verify, and can be skipped by the respondent regardless: it is a
   burden reduction, not an extra gate. See [PROIT](#proit--pre-interview-profiling).
7. **R07 Participation choice** — complete it now (web self-administration), have a
   researcher call, or a WhatsApp-assisted session.
8. **R08 Kobo questionnaire redirect** — requires **both** a passed eligibility check and
   `GIVEN` participation consent, enforced server-side in
   `apps.kobo.services.build_redirect_url()` — the single point every caller goes through,
   not a disabled button. Launches the actual KoboToolbox form with `Master_ID`,
   `Sample_ID`, administration mode, role category and a non-identifying token reference
   passed as hidden fields.
9. **R09 Appointment request** — if the respondent asked for a call instead, this
   captures a preferred time/mode. Also consent-gated (PI decision, Sep 2026): an
   appointment records a named person's availability against an identified organisation
   and places them on an RA's call list, so it sits behind the same gate as the
   self-administered route. Times must be in the future, enforced at both layers.
10. **R10 Completion** — a neutral closing page. Someone who completed the questionnaire
    is thanked for participating; someone who booked a call is told a researcher will be
    in touch, since they have *not* finished. No score, rating, or financing decision is
    ever shown here or anywhere else in this flow.

Every step reports failure in plain language and leaves the respondent able to retry.
Before the Sep 2026 audit each step wrapped its submit in `try/finally` with no `catch`,
so an expired token, a throttled request or a dropped connection left the button
re-enabled and the page unchanged — indistinguishable from a dead button, to someone
with no support channel open.

### 3. KoboToolbox integration (the actual questionnaire)

KoboToolbox is the sole authority for the QUAN questionnaire's logic and capture — this
app never re-implements branching or validation. The catch: **Kobo's webhook only fires
on new-submission creation, never on a later edit**. Relying on it alone would silently
lose every RA correction or respondent edit made after first submission. So:

- The webhook (`POST /api/v1/kobo/webhook/`, shared-secret protected) is only ever a
  fast "heads-up" that triggers an early reconciliation run — it never writes
  `QUANSubmission` rows itself.
- A **Celery Beat scheduled job** (every 15 minutes during active fieldwork hours, 60
  overnight — both configurable) is the actual source of truth: it pulls the full
  submission list from Kobo's `/api/v2/assets/{asset_uid}/data/` endpoint (following
  pagination — see [Notable fixes](#notable-fixes)), computes a
  content hash of each payload, and treats any change in that hash as an edit, re-queuing
  the submission for QA review rather than silently keeping a stale QA status.
- A submission whose `sample_id` doesn't match any known `SampleCase` is flagged as a
  mismatch and audited — never dropped, never auto-matched to the nearest case.
- Admins can also trigger a pull on demand from the **"KoboToolbox sync"** panel on the
  QA queue screen (`/admin/qa`) instead of waiting for the next scheduled tick.

### 4. QA and the Research Operations Centre (`/admin/*`, screens A01–A12)

Internal staff sign in at `/admin/login` (JWT-based, httpOnly cookies — the token itself
is never exposed to client-side JavaScript; see [Authentication](#authentication)).
There are **eight roles**, and each internal endpoint checks a specific one, never just
"is logged in."

**Navigation is scoped to the role.** `backend/api/navigation.py` is the single source of
truth for role → screens, served to the frontend by `GET /api/v1/auth/me/`. The nav bar
renders exactly that list — it is not a full menu with some entries disabled — and each
role lands on its own first screen at sign-in. A screen outside your role renders an
explicit "not part of your role" card rather than a page whose every fetch 403s. This is
UX only; the permission classes remain the real boundary.

| Role | Screens | Lands on |
|---|---|---|
| PI / Admin | 15 (everything) | `/admin/dashboard` |
| Field Coordinator | 14 (no Audit Log) | `/admin/dashboard` |
| Supervisor (read-only) | 13 (no Audit Log or Export) | `/admin/dashboard` |
| Analyst (read-only) | 6 (dashboards, Cost, Export) | `/admin/dashboard` |
| Contact RA | 2 (Main-400 Register, Appointments) | `/admin/sample` |
| QUAN/Kobo QA RA | 2 (QA Dashboard, QA Queue) | `/admin/dashboard/qa` |
| KII RA | 2 (KII/Doc Dashboard, KII Register) | `/admin/dashboard/kii-documents` |
| Documentary RA | 2 (KII/Doc Dashboard, Documents) | `/admin/dashboard/kii-documents` |

The three RA roles are deliberately **not** interchangeable — see
[Notable fixes](#notable-fixes) for the over-grant this replaced. Read-only roles see
figures and lists on mixed screens but not the forms or buttons
(`components/admin/RoleGate.tsx`).

| Screen | Route | Purpose |
|---|---|---|
| A01 | `/admin/login` | Internal sign-in |
| A02 | `/admin/dashboard` | Executive dashboard — overall progress vs. the 400/60/50–75 targets, days to data lock, coverage gaps by stratum |
| — | `/admin/dashboard/sampling` | Main-400 by province, verified/total by stratum, reserve activations by reason |
| — | `/admin/dashboard/contact` | Organisations verified, invitations sent/opened, appointments, refusals |
| — | `/admin/dashboard/qa` | Submissions today/cumulative, QA queue depth, decisions recorded, administration-mode split |
| — | `/admin/dashboard/kii-documents` | KII and document progress vs. targets |
| — | `/admin/organisations` | Register an organisation and create its sample case |
| A03 | `/admin/sample` | Main-400 / Reserve register |
| A04 | `/admin/sample/[sampleId]` | Case detail: assigned Contact RA, matched Reserve, PROIT pre-profile, invitations, workflow transitions, contact-attempt log |
| A05 | `/admin/appointments` | Appointment queue with status transition buttons |
| A06 | `/admin/qa` | QUAN QA decision queue (accept / re-query / reject) plus the KoboToolbox sync panel |
| A07 | `/admin/kii`, `/admin/kii/new`, `/admin/kii/[id]` | KII register, creation, and per-record status/consent/transcript/coding workflow |
| A08 | `/admin/documents`, `/admin/documents/new`, `/admin/documents/[id]` | Documentary evidence corpus, authenticity assessment gate before a document can be included |
| A09 | `/admin/reserve` | Reserve activation (five authorised reasons, mandatory evidence note) |
| A10 | `/admin/cost` | Fieldwork cost dashboard and entry form |
| A11 | `/admin/audit` | Full audit log — every sensitive action, correctly attributed to the admin who performed it |
| A12 | `/admin/export` | De-identified analysis export and full operational export (CSV) |
| — | `/admin/proit/[id]` | Researcher pre-profile review and lock (see [PROIT](#proit--pre-interview-profiling)) |
| — | `/admin/account` | Change your own password (available to every role) |

Every register screen (`/admin/sample`, `/admin/organisations`, `/admin/kii`,
`/admin/documents`, `/admin/appointments`, `/admin/reserve`, `/admin/audit`) paginates at
20 rows with Previous/Next controls, and most carry a `?search=` box wired to DRF's
`SearchFilter`. Before Sep 2026 none of them had either, so with 400 Main cases loaded
every row past the first twenty was unreachable from the UI.

Human QA decisions (accept / re-query / reject) always require a note and are the only
way a submission reaches `QA_PASSED` — there is no automatic pass path. A KII cannot be
marked completed with a recording unless **recording consent** was captured as its own,
separate decision from participation consent (never inferred from it).

### PROIT — pre-interview profiling

PROIT (Pre-Interview Respondent & Organisation Intelligence and Verification Tool,
`backend/apps/proit/`, spec in `docs/30_PROIT_MODULE.md`) shortens the interview by
establishing publicly available background facts *before* contact, so the respondent
confirms or corrects them rather than answering from zero.

- A researcher records each fact with its source, date, locator and confidence
  (HIGH/MODERATE/LOW), drawing on a four-tier source-authority hierarchy — statutory
  registers, then official reports, then reputable media, then corroborated public
  content. Evidence records carry `EVID-<5>` identifiers.
- A second researcher reviews and **locks** the profile (`/admin/proit/[id]`) before the
  respondent is contacted.
- Three values stay permanently separate and are never merged: the documentary value, the
  respondent's own answer, and the researcher's reconciled value.
- On the KII side an **adaptive gap engine** generates interview questions only for what
  is still genuinely unresolved.
- It can never pre-fill, skip or infer any frozen ABI/NFM/Digital-Readiness/FST scale
  item — only non-core descriptive background.

Respondent-facing PROIT is gated behind `PROIT_ENABLED_FOR_RESPONDENTS`, currently on.
That flag was flipped on the PI's own documented **risk acceptance**, which is recorded
as exactly that in `docs/30_PROIT_MODULE.md` — it is not an ethics or change-control
clearance, and the distinction is deliberate.

### 5. Exports and the audit trail

Two CSV exports exist, with a deliberately different schema:

- **De-identified analysis export** (`/admin/export` → "Download analysis export") —
  `sample_id, master_id, province, actor_family, value_chain, size_class,
  administration_mode, qa_status, submitted_at, completion_seconds`. No name, phone,
  email or gatekeeper field ever appears here. Safe to share with the wider research
  team.
- **Full operational export** — the same columns plus `organisation_name,
  respondent_full_name, respondent_phone, respondent_email, gatekeeper_name,
  gatekeeper_contact`. Internal fieldwork operations use only, PI/Admin role required.

Every sensitive action — consent recorded, invitation issued, reserve activated, KII
status changed, document authenticity/QA decision, a rejected invalid workflow
transition — writes an `AuditEvent` row visible at `/admin/audit`, correctly attributed
to the signed-in user who performed it (see [Notable fixes](#notable-fixes)).

### Authentication

Login (`POST /api/auth/login`, a Next.js route) exchanges credentials for a JWT via
Django's `/api/v1/auth/token/`, then sets it as an **httpOnly cookie** — the token value
never reaches client-side JavaScript. Every subsequent internal API call goes through
`/api/proxy/[...path]` (also a Next.js route), which reads the cookie server-side and
attaches the `Authorization: Bearer` header before forwarding to Django. The frontend
component code never handles a raw token.

---

## Architecture at a glance

```
Browser
  │
  ▼
Nginx  (research.agribizframework.com, TLS via Certbot)
  ├── /api/v1/, /api/schema/, /api/docs/   → Django + gunicorn (127.0.0.1:8100)
  ├── /django-admin/                        → Django + gunicorn (127.0.0.1:8100)
  ├── /static/, /media/                     → served from disk
  ├── /api/auth/*, /api/proxy/*             → Next.js (127.0.0.1:3100)  ← Next's own routes, NOT Django
  └── /  (everything else)                  → Next.js (127.0.0.1:3100)
```

- **Backend**: Django 5.1 + Django REST Framework, Python 3.12, PostgreSQL, 13 apps
  (`accounts, sampling, contacts, consent, invitations, kobo, messaging, kii, evidence,
  qa, dashboards, costs, audit`).
- **Frontend**: Next.js 15 (App Router) + TypeScript, Tailwind, TanStack Query.
- **Background jobs**: Celery + Redis, for Kobo reconciliation and the reminder queue
  (`--pool=solo --concurrency=1` in production — the VPS shares its memory budget with a
  sibling project, `docs/27_AGENT_EXECUTION_PLAN.md` Phase 10).
- **Same VPS, separate app**: shares infrastructure with the sibling ABI project
  (`docs/20_EMBEDDING_WITH_ABI.md`) but a completely separate database, Nginx
  `server{}` block, and systemd units — no shared code, no navigational link between
  the two.

---

## Quick start (local development)

Backend (Django + DRF, needs PostgreSQL 16+):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env                              # edit DATABASE_URL, KOBO_* etc. -- see below
python manage.py migrate
python manage.py seed_drp_dev                      # dev fixtures: strata, synthetic cases, one account per role
python manage.py runserver
```

Frontend (Next.js 15 + TypeScript, needs the backend running):

```bash
cd frontend
npm install
cp .env.example .env                               # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

Then open `http://localhost:3000` for the respondent-facing flow, or
`http://localhost:3000/admin` for the Research Operations Centre. `seed_drp_dev` prints
its credentials to the console: `e2e_admin` (PI/Admin) plus one `e2e_<role>` account for
each of the other seven roles, all sharing the same password. Signing in as each is the
quickest way to see the role-scoped navigation described above.

Background jobs (optional for most local work — only needed to actually exercise Kobo
reconciliation or the reminder queue):

```bash
# needs Redis running locally
cd backend
celery -A config worker --loglevel=info --pool=solo
celery -A config beat --loglevel=info
```

## Environment variables

**Backend** (`backend/.env`, see `backend/.env.example` for the full template):

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` locally, `config.settings.prod` in production |
| `DJANGO_SECRET_KEY` | Django's cryptographic signing key |
| `DJANGO_DEBUG` | Must be `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed `Host` headers |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `JWT_SIGNING_KEY`, `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`, `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Auth token config |
| `INVITATION_TOKEN_BYTES`, `INVITATION_TOKEN_EXPIRY_DAYS` | Invitation token generation |
| `KOBO_API_BASE_URL` | Kobo server, e.g. `https://kf.kobotoolbox.org` |
| `KOBO_API_TOKEN` | Kobo API token — **server-side only, never sent to the frontend** |
| `KOBO_ASSET_UID` | The production Kobo asset (form) UID |
| `KOBO_WEBHOOK_SHARED_SECRET` | Validates `POST /api/v1/kobo/webhook/` |
| `KOBO_RECONCILIATION_INTERVAL_MINUTES` | Celery Beat pull frequency |
| `WHATSAPP_API_BASE_URL`, `WHATSAPP_API_TOKEN`, `WHATSAPP_BUSINESS_ACCOUNT_ID` | WhatsApp Business Platform (blocked on Meta template approval — see Status) |
| `CELERY_BROKER_URL` | Redis URL |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Must match the deployed frontend origin exactly |
| `BACKUP_RPO_HOURS`, `BACKUP_RTO_HOURS` | Documented targets for `deploy/backup.sh` |

**Frontend** (`frontend/.env`, see `frontend/.env.example`):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_APP_DOMAIN` | The deployed domain |
| `NEXT_PUBLIC_API_BASE_URL` | Where the frontend's own `/api/proxy` route forwards to (Django's `/api/v1`) |
| `NEXT_PUBLIC_APP_ENV` | `development` / `production` |

Never commit real values for any of the above — both `.env` files are gitignored, and
`*.env.production` is gitignored too.

## Tests

```bash
cd backend  && pytest              # 260 tests: unit, API, privacy, role/navigation, gates, throttling, Kobo
cd backend  && ruff check .        # linting
cd frontend && npx tsc --noEmit    # type checking
cd frontend && npm run lint        # eslint
cd frontend && npm run test        # Vitest component tests
cd frontend && npx playwright test # E2E: 26 specs (25 run, 1 intentionally skipped -- see below)
```

The Playwright suite covers the respondent flow (invitation → consent → Kobo redirect)
and its failure branches, privacy/reserve-lock invariants, role-scoped navigation per
role, and every admin panel: workflow transitions and contact-attempt logging,
appointment status, the cost-entry form, the KII recording-consent gate, the document
authenticity-before-inclusion gate, reserve activation, and the Kobo sync panel's
graceful degradation when no real Kobo asset is configured.

Two things worth knowing before adding tests here:

- `manage.py seed_drp_dev` creates **one account per role** (`e2e_admin`, plus
  `e2e_<role>` for the other seven, same password), which is what
  `e2e/role-scoped-navigation.spec.ts` signs in as. Fixtures that tests mutate (workflow
  status, reserve activation) are force-reset on every seed run, so the suite stays
  reliable against a shared, never-reset local database.
- **A test asserting that a gate refuses something must not use the shared seed case.**
  Consent and eligibility both attach to the `SampleCase`, so by the second run it
  already has GIVEN consent and eligible respondents on it, and the refusal silently
  never fires. Use `issueTokenOnFreshCase()` from `e2e/helpers.ts`, which builds its own
  organisation and case. Two specs were caught passing for this reason.

One spec (`e2e/pi-blocked-items.spec.ts`) is deliberately `test.skip`, not absent: the
WhatsApp Business Platform integration has no code surface yet (no Meta-approved account
or template). It stays visible with a written reason in every run's report until the
underlying external action happens. (The POTRAZ/data-protection determination was
tracked here too; resolved 2026-09-12, see `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md`.)

A full manual QA pass (this hardening round) also walked every respondent-flow screen
and every admin screen in a real browser against a freshly seeded local database, and
separately against production — see [Notable fixes](#notable-fixes).

## Deployment

Production is `research.agribizframework.com`, a single VPS shared with the sibling ABI
project (own database, own Nginx `server{}` block, own systemd units — see
`docs/20_EMBEDDING_WITH_ABI.md`).

```bash
# On the server, as root, after copying the updated code to /srv/agribiz-drp/:
sudo bash /srv/agribiz-drp/deploy/deploy.sh
```

`deploy.sh` backs up the database, installs backend/frontend dependencies, runs
migrations, builds the frontend, restarts all four systemd units
(`drp-backend`, `drp-frontend`, `drp-celery-worker`, `drp-celery-beat`), validates the
Nginx config without overwriting Certbot's HTTPS block, and runs health checks against
the backend, frontend, and the full HTTPS path through Nginx — it fails loudly (and
tells you where to look) rather than reporting success on a partial deploy. To roll
back: `sudo bash /srv/agribiz-drp/deploy/rollback.sh`.

**Nginx routing** — the one part of this stack that is easy to get subtly wrong, since
Django and Next.js both technically live under `/api/` (see
[Notable fixes](#notable-fixes) for what happens if you don't
get this right):

```
/api/v1/, /api/schema/, /api/docs/   → Django   (gunicorn, 127.0.0.1:8100)
/django-admin/                        → Django   (gunicorn, 127.0.0.1:8100)
/static/, /media/                     → served from disk by Nginx directly
/api/auth/*, /api/proxy/*             → Next.js  (127.0.0.1:3100) -- NOT Django
/  (everything else)                  → Next.js  (127.0.0.1:3100)
```

### Production verification

After any deploy, confirm (not just "curl returns 200" — confirm the feature actually
works):

1. `https://research.agribizframework.com/` loads the public respondent landing page.
2. `https://research.agribizframework.com/admin/login` → sign in → the Executive
   Dashboard actually renders (not a permanent spinner, not a console 404 on
   `/api/auth/me` or `/api/proxy/...` — see the nginx note above).
3. `systemctl status drp-backend drp-frontend drp-celery-worker drp-celery-beat nginx`
   all report `active`.
4. `sudo journalctl -u drp-backend -n 50 --no-pager` has no repeating errors.
5. A test action (e.g. the "Sync now" Kobo panel on `/admin/qa`) round-trips through
   Nginx → Next.js *or* Django correctly depending on which route it hits.

### Troubleshooting

| Symptom | Likely cause | Where to look |
|---|---|---|
| Login succeeds but the dashboard never loads / spins forever | Nginx routing `/api/auth/` or `/api/proxy/` to Django instead of Next.js | `sudo journalctl -u drp-backend` for 404s on those exact paths; check `/etc/nginx/conf.d/research.agribizframework.conf` against the table above |
| "Sync now" always fails | No real `KOBO_ASSET_UID`/`KOBO_API_TOKEN` configured yet (expected pre-go-live), or the Kobo account/token is invalid/expired | The error message on the panel itself now shows the actual Kobo API error (e.g. a 404 with an empty asset segment means the UID isn't set) |
| An admin's actions show up as "system" in the audit log | Should not happen after this hardening pass (`apps/audit/middleware.py`) — if it recurs, check that `AuditContextMiddleware` is still listed in `MIDDLEWARE` in `config/settings/base.py` | `backend/tests/test_audit.py` |
| A workflow/appointment/contact-event admin action 400s | Check whether a serializer field that should be server-resolved (from the URL, or from the state machine) was accidentally made writable again | `backend/tests/test_sample_case_api_integrity.py`, `test_appointment_status.py`, `test_contact_event_api.py` |
| `npm ci` fails with `EACCES: mkdir '/home/agribiz-drp'` | The `agribiz-drp` system user has no writable `$HOME` for npm's cache | `deploy/setup-server.sh` creates this directory explicitly; re-run it, or `mkdir -p /home/agribiz-drp && chown agribiz-drp:agribiz-drp /home/agribiz-drp` |

## Notable fixes

Every item below has a regression test. Where a test already existed but was passing for
the wrong reason, that is called out — those were the most dangerous cases, because the
green tick was the reason nobody looked.

### Second pass — role, register and respondent-flow audit (Sep 2026)

1. **The eligibility gate was documented but never enforced.**
   `build_redirect_url()` stated in its own docstring that it issues no questionnaire URL
   "without a passed eligibility check and GIVEN participation consent", and
   `docs/28_DEFINITION_OF_DONE.md` says an ineligible respondent is *never* routed to the
   questionnaire. Only consent was checked. Since `/api/v1/consent/` is `AllowAny` with a
   valid token as its only credential, anyone the eligibility screen turned away could
   POST consent directly and be handed a Kobo URL. The test that appeared to cover this
   passed only because it never gave consent — its own comment admitted as much. Fixed in
   `build_redirect_url()` via `contacts.services.has_passed_eligibility`.
2. **`IsQAOrAdmin` was shared across three unrelated modules**, so a KII RA could edit
   documentary evidence and a Documentary RA could take QUAN QA decisions. Split into
   `IsQAOrAdmin` / `CanManageKII` / `CanManageDocuments`.
3. **The KII/document dashboard excluded the very RAs it is for** — it used
   `IsAnalystOrAdmin`, refusing the KII and Documentary RAs that
   `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` grants it to.
   Now `CanViewKIIDocumentDashboard`.
4. **`/api/v1/dashboards/qa/` had no page at all**, so the QUAN QA RA's nav entry pointed
   at a 404. Built as `/admin/dashboard/qa`.
5. **Every role saw all 14 nav links and landed on `/admin/dashboard`**, which four of
   the eight roles are refused. Replaced by `backend/api/navigation.py` as the single
   source of truth, served via `GET /api/v1/auth/me/`.
6. **Registers were unusable at real volumes** — 20 rows per page, no paging control, no
   search, against 400 Main + 400 Reserve + 90 KII + 100 documents. Also, `KIIRecord` and
   `DocumentRecord` had no `Meta.ordering`, so page boundaries were arbitrary and a row
   could appear on two pages or none.
7. **Sign-in shared the generic 30/min anon throttle** with the public respondent
   endpoints. A team behind one office NAT is one IP, so staff logins competed with
   respondent traffic — and DRF's 429 reached the login screen as "Invalid username or
   password". Own scope, and the login route now distinguishes throttling from bad
   credentials.
8. **Every respondent-flow step failed silently** — `try/finally` with no `catch`, so a
   failed request left the button re-enabled and the page unchanged. Worst on consent,
   where the respondent could not tell whether their decision had been recorded.
9. **Appointments could be requested in the past**, landing in the RA's queue already
   missed. Guarded in the picker, re-checked in the page, enforced server-side.
10. **Appointment requests are now consent-gated** (PI decision) — see the respondent
    flow above.
11. **`matched_case` was a bare FK with no validation**, so the API would accept a Main
    paired to another Main, a case paired to itself, or the same Reserve claimed by two
    different Main cases — the last silently breaking the reserve lock. Now routed
    through `sampling.services.set_matched_case` with an audit entry, and exposed as a
    picker on the case detail page instead of requiring Django admin.
12. **A DRF `ValidationError` returned "An error occurred."** with the real text buried in
    `field_errors`, which the respondent flow has no UI for. The envelope now surfaces the
    first field error as the message.

### First pass — end-to-end QA hardening (Sep 2026)

Every respondent-flow and admin screen exercised by hand in a real browser, every
endpoint cross-checked against its documented contract.

1. **Production routing bug (the highest-impact fix)**: Nginx's `location /api/` caught
   *everything* under `/api/`, including the frontend's own `/api/auth/*` and
   `/api/proxy/*` routes (Django only ever mounts `/api/v1/`, `/api/schema/`,
   `/api/docs/`). Confirmed live via `journalctl` that a real visitor had been getting a
   404 on every login and every dashboard fetch for hours. Fixed by routing only
   Django's actual prefixes to the backend and letting the frontend's routes fall
   through to the existing catch-all `location /`.
2. **Audit trail always said "system"**: `AuditContextMiddleware` read `request.user`
   before DRF's JWT authentication had run, so every `AuditEvent` in the system's history
   was attributed to no one. Fixed by reading it lazily, once authentication has
   actually populated it.
3. **`PATCH /api/v1/sample-cases/{id}/` could bypass the S00–S16 state machine
   entirely** — jumping a case straight to `Completed` with no validation and no audit
   trail. Fixed by making the state-machine-controlled fields read-only and adding a
   dedicated, validated transition endpoint.
4. **Appointments had no way to be confirmed/completed/cancelled** by an RA — `status`
   was correctly read-only against public tampering, but that also blocked legitimate
   internal updates. Added a dedicated status endpoint.
5. **The admin "log a contact attempt" form always failed** with a 400 — the serializer
   required a field (`sample_case`) that the view resolves from the URL and was never
   meant to be supplied by the caller.
6. **KII consent gave no visual feedback** — recorded consent decisions existed on the
   model but weren't exposed by the API, so the admin screen couldn't show whether
   participation/recording consent had already been captured.
7. **Kobo pagination** — `fetch_submissions()` only ever read the first page of Kobo's
   paginated data endpoint.
8. **Kobo outages crashed instead of degrading gracefully** — an unreachable Kobo API
   propagated as a raw 500 instead of a clean, informative error.

## Repository layout

```
Digital_Respondent_Portal/
├── AGENTS.md
├── README.md
├── docs/
│   └── tools/    # build_guide.py -- builds the end-user guide PDF (PDF itself gitignored)
├── deploy/       # deploy.sh, backup.sh, rollback.sh, setup-server.sh, env templates
├── nginx/        # research.agribizframework.conf (source of truth, mirrored on the VPS)
├── systemd/      # drp-backend, drp-frontend, drp-celery-worker, drp-celery-beat unit files
├── frontend/     # Next.js + TypeScript
└── backend/      # Django + Django REST Framework
```

Same two-folder (`frontend/`, `backend/`) shape as the sibling ABI project — see
`docs/03_SYSTEM_ARCHITECTURE.md` § Repository layout and `docs/20_EMBEDDING_WITH_ABI.md`
for how the two projects share infrastructure without sharing a codebase.

## Documentation

- `AGENTS.md` — ground rules for anyone (human or agent) modifying this codebase; the
  Main-400/Reserve-400 sample, workflow statuses, identifier scheme and QA thresholds
  are fixed research-operations logic and must never be silently changed.
- `docs/INDEX.md` — full documentation index and reading order.
- `docs/06_API_ARCHITECTURE.md` — full endpoint reference.
- `docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md` — Master_ID/Sample_ID generation and the
  full S00–S16 state machine.
- `docs/11_KOBOTOOLBOX_INTEGRATION.md` — Kobo integration design, including the
  reconciliation-vs-webhook decision and this pass's pagination/resilience fixes.
- `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` — consent model, audit requirements,
  de-identified vs. operational export schema.
- `docs/27_AGENT_EXECUTION_PLAN.md` — phased, checkable build task list.
- `docs/28_DEFINITION_OF_DONE.md` — acceptance criteria and go-live checklist.
- `docs/29_RESPONDENT_GUIDE_AND_MESSAGING.md` — the plain-language respondent journey,
  ready-to-use WhatsApp/email/manual-code invitation message templates, and an RA
  troubleshooting table — practical companion to the "Send Invitation" panel.
- `docs/30_PROIT_MODULE.md` — the pre-interview profiling tool: field modules, the
  source-authority hierarchy, the three-value architecture, and the record of the PI's
  risk-acceptance decision to enable it for respondents.
- `backend/api/navigation.py` — not documentation as such, but the single source of truth
  for which role sees which screens. Change it there and nowhere else;
  `backend/tests/test_role_navigation.py` and `frontend/e2e/role-scoped-navigation.spec.ts`
  will tell you if the API permissions disagree.

### The end-user guide

`docs/tools/build_guide.py` builds a complete, non-technical **user guide PDF** for the
research team — sign-in, what each role sees, every screen, inviting a respondent, the
respondent's experience, a full walkthrough and troubleshooting. The script is the
tracked source of truth; the PDF it writes alongside itself is gitignored.

```bash
backend/.venv/Scripts/python.exe docs/tools/build_guide.py   # Windows
backend/venv/bin/python docs/tools/build_guide.py            # Linux/macOS
```

Bump `REVISION` in that script whenever the content changes, so a printed or emailed copy
can be told apart from an earlier one.

## Domain

Live at `research.agribizframework.com` (shares the ABI project's production host and
TLS setup, deployed with its own Nginx server block, database, and systemd services —
see `docs/20_EMBEDDING_WITH_ABI.md`).

The real Main-400/Reserve-400, KII and documentary-evidence registers **are** loaded, but
no invitation has been issued and no consent recorded — go-live (Phase 11) requires
explicit PI sign-off per `docs/28_DEFINITION_OF_DONE.md`. Treat the production database as
holding real, identifying research data: it is not a scratch environment.
