# ABF-FST Digital Respondent Portal — v1.0 (planning)

A research-operations platform supporting *"Developing and Validating the Agribusiness
Bankability Framework for Food Systems Transformation through Novel Financing Models in
Zimbabwe"* (ABF-FST). Sponsored for development by GigaFood Africa. Principal
Researcher: Happyson Saina, Doctor of Strategic Management, Chinhoyi University of
Technology (Supervisors: Dr L. Chikazhe, Dr J. Kanyepe).

The portal authenticates and routes the study's selected Main-400 respondents (plus a
locked Reserve-400), captures consent and eligibility, launches the KoboToolbox
questionnaire with controlled identifiers, reconciles submissions, and runs the KII,
documentary-evidence, contact/CRM, QA and fieldwork-cost operations behind the 400 QUAN
/ 60 KII / 50–75 document data-collection target. It is **not** a public survey tool and
does **not** expose any ABI bankability score to respondents — see
`docs/00_PROJECT_MASTER.md` for full project identity and `docs/20_EMBEDDING_WITH_ABI.md`
for why it is deliberately kept separate from the public ABI self-assessment demo.

## Status

**Planning / pre-build.** This documentation set and `docs/27_AGENT_EXECUTION_PLAN.md`
exist so the Principal Researcher can review and approve the design before any code is
written — see `AGENTS.md` ground rule 1. No code has been scaffolded yet.

This is a research-operations tool supporting an active fieldwork study with a hard
30 November 2026 data-lock date — not a production lending or credit-decision system.
See `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md` for the compliance position and
`docs/02_PRODUCT_REQUIREMENTS.md` for what is explicitly out of scope.

## Quick start (once approved and scaffolded)

Backend (Django + DRF, needs PostgreSQL — see `backend/README.md`):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env                              # edit DATABASE_URL, KOBO_API_TOKEN etc.
python manage.py migrate
python manage.py seed_drp_dev                      # dev fixtures: test strata, synthetic cases
python manage.py runserver
```

Frontend (Next.js 15 + TypeScript, needs the backend running — see `frontend/README.md`):

```bash
cd frontend
npm install
cp .env.example .env                               # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

Then open `http://localhost:3000` for the respondent-facing flow, or
`http://localhost:3000/admin` for the Research Operations Centre (internal login
required).

## Tests

```bash
cd backend  && pytest              # unit + API + privacy + token/consent-gate tests
cd frontend && npm run test        # Vitest component tests
cd frontend && npx playwright test # E2E: invitation → consent → Kobo redirect → reconciliation
```

## Repository layout

```
abf-fst-respondent-portal/
├── AGENTS.md
├── README.md
├── docs/
├── frontend/     # Next.js + TypeScript
└── backend/      # Django + Django REST Framework
```

Same two-folder shape as the sibling ABI project (`agribusiness-bankability/`) — see
`docs/03_SYSTEM_ARCHITECTURE.md` § Repository layout and `docs/20_EMBEDDING_WITH_ABI.md`
for how the two projects share infrastructure without sharing a codebase.

## Documentation

- `AGENTS.md` — ground rules for anyone (human or agent) modifying this codebase; the
  Main-400/Reserve-400 sample, workflow statuses, identifier scheme and QA thresholds
  are fixed research-operations logic and must never be silently changed.
- `docs/INDEX.md` — full documentation index and reading order.
- `docs/27_AGENT_EXECUTION_PLAN.md` — phased, checkable build task list.
- `docs/28_DEFINITION_OF_DONE.md` — acceptance criteria.

## Domain

Planned subdomain: `research.agribizframework.com` (shares the ABI project's production
host and TLS setup but is not cross-linked with it) — see
`docs/20_EMBEDDING_WITH_ABI.md` and `docs/24_ENVIRONMENT_CONFIGURATION.md`.
