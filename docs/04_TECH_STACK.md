# 04 — Tech stack

Matches the sibling ABI project's stack exactly, by explicit decision (shared
infrastructure, shared developer familiarity, shared hosting — see
`20_EMBEDDING_WITH_ABI.md`).

| Layer | Technology | Notes |
|-------|------------|-------|
| Web UI | Next.js 15+ (App Router) + TypeScript | Single responsive codebase; PWA not required (unlike ABI) since the QUAN capture itself happens inside Kobo, not this app — see "What NOT to add" below |
| Styling | Tailwind CSS | Utility-first, matches `21_UI_UX_GUIDELINES.md` tokens |
| UI components | shadcn/ui | Same component approach as ABI |
| Charts | Recharts | Coverage/QA/cost dashboards |
| Data fetching / cache | TanStack Query | Server-state cache for API calls |
| Client state | Zustand (or React Context) | In-progress consent/eligibility wizard state before the Kobo handoff |
| Forms | React Hook Form + Zod | Validation matching backend serializers |
| API framework | Django 5.x + Django REST Framework | Python 3.12+ |
| Auth | JWT via `djangorestframework-simplejwt` | Internal users only; public respondents use invitation tokens, not accounts — see `10_INVITATION_AND_CONSENT.md` |
| Database | PostgreSQL 15+ | Separate database instance/schema from the ABI project's `abi_db` (see `03_SYSTEM_ARCHITECTURE.md`) |
| Filtering | `django-filter` | Sampling/contact/QA dashboard queries |
| API docs | `drf-spectacular` (OpenAPI) | Served at `/api/schema/` and `/api/docs/` |
| External integration | KoboToolbox REST API + REST Services webhook | See `11_KOBOTOOLBOX_INTEGRATION.md` |
| Messaging | WhatsApp Business Platform (Meta Cloud API) or a Business Solution Provider fronting it | See `12_CONTACT_CRM_AND_MESSAGING.md` |
| Async tasks | Celery + Redis, for the scheduled Kobo reconciliation job and reminder-queue dispatch | **The one place this project needs what ABI explicitly deferred** — the reconciliation poll and reminder dispatch are genuinely periodic background jobs, not request/response work. Use Celery Beat for scheduling. Do not add Celery for anything else without a matching justification. |
| PDF/export generation | ReportLab (registers, de-identified export) | Same library choice as ABI's respondent report |
| Backend tests | pytest + pytest-django | Token/consent-gate/reserve-lock logic must have exact-behaviour unit tests |
| E2E tests | Playwright | Invitation → eligibility → consent → Kobo redirect → reconciliation flow |
| Reverse proxy | Nginx | Shared instance with ABI in production, separate `server{}` block per subdomain |
| HTTPS | Let's Encrypt / Certbot | Same pattern as ABI — see the "127.0.0.1 lesson" in the ABI project's `PRODUCTION_ARCHITECTURE.md`, which applies unchanged here |
| Hosting | Same Linux VPS as ABI, or a second small VPS if resource contention becomes an issue | Decide at Phase 0 — see `23_DEPLOYMENT_ARCHITECTURE.md` |
| Package manager (frontend) | pnpm or npm — match whichever the ABI project settled on | |
| Package manager (backend) | pip + `venv`, `requirements/` split by environment | |

## Version pinning

Pin major versions in `package.json` / `requirements/*.txt` at scaffold time (Phase 0 of
`27_AGENT_EXECUTION_PLAN.md`) and record the exact versions used in `README.md`. Do not
silently upgrade a dependency mid-build, matching ABI's own policy.

## What NOT to add in v1.0

- No native mobile SDKs — a responsive web app is sufficient (original blueprint's own
  Architecture Rule).
- No GraphQL — REST only.
- No separate microservices for KII/documents/QA/messaging — they are Django apps inside
  the single `backend/` service.
- No full offline-first PWA service-worker architecture for the respondent flow itself —
  unlike ABI's 10–12 minute in-app assessment, this portal's respondent surface is a
  short consent/eligibility/routing flow (see `07_FRONTEND_ARCHITECTURE.md`), and the
  actual 10–12 minute questionnaire capture happens inside Kobo's own client, which has
  its own offline handling. Re-evaluate only if `26_MVP_PHASING_AND_ROADMAP.md` Phase 2
  data shows respondents losing consent/eligibility progress to connectivity drops.
- No automated (human-unsupervised) WhatsApp sending beyond the approved reminder
  sequence — see `12_CONTACT_CRM_AND_MESSAGING.md`.
