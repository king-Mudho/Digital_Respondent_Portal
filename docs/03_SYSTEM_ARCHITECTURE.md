# 03 — System architecture

## Top-level component view

```
┌──────────────────────────────────────────────────────────────┐
│                  DRP FRONTEND                                  │
│              Next.js + TypeScript                              │
│                                                                  │
│  Respondent flow (R01-R10) │ Research Ops Centre (A01-A12)      │
└─────────────────────────┬──────────────────────────────────────┘
                           │  REST (JSON, /api/v1)
┌─────────────────────────▼──────────────────────────────────────┐
│                  DRP BACKEND                                    │
│              Django + Django REST Framework                     │
│                                                                    │
│ ┌────────────┐ ┌─────────────┐ ┌──────────────────────────────┐│
│ │ Sampling   │ │ Identity &  │ │ Consent & Eligibility         ││
│ │ Service    │ │ Contact Svc │ │ Service                       ││
│ └────────────┘ └─────────────┘ └──────────────────────────────┘│
│ ┌────────────┐ ┌─────────────┐ ┌──────────────────────────────┐│
│ │ Kobo       │ │ QA Engine   │ │ KII / Documentary Evidence    ││
│ │ Integration│ │             │ │ Service                       ││
│ └────────────┘ └─────────────┘ └──────────────────────────────┘│
│ ┌────────────┐ ┌─────────────┐ ┌──────────────────────────────┐│
│ │ Dashboard  │ │ Messaging   │ │ Audit & Cost Service           ││
│ │ / Reporting│ │ (WhatsApp)  │ │                                ││
│ └────────────┘ └─────────────┘ └──────────────────────────────┘│
└─────────────────────────┬────────────────────────┬──────────────┘
                           │                        │
                           ▼                        ▼
                   ┌───────────────┐        ┌───────────────┐
                   │  PostgreSQL   │        │  KoboToolbox   │
                   │  (this app)   │        │  (external)    │
                   └───────────────┘        └───────────────┘
```

**Rule**: the frontend renders and collects input; the backend is the sole authority for
token validity, eligibility, consent state, workflow status and QA decisions. KoboToolbox
is the sole authority for QUAN form logic and capture — this backend never re-implements
questionnaire branching.

## Deployment topology

```
Domain: research.agribizframework.com   (subdomain of the ABI production host)
        │
        ▼
   Nginx / HTTPS (Let's Encrypt, same certificate-management pattern as ABI)
        │
        ├──────────────► Next.js frontend (build + serve)
        │
        └──────────────► Django REST API (Gunicorn)
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
               PostgreSQL          KoboToolbox API
             (drp_db, separate     (scheduled pull +
              database from        REST Services
              the ABI project's    webhook heads-up)
              abi_db)
```

Shares the physical host, Nginx instance and TLS setup with the ABI project in
production (cost containment — see the original blueprint's own Section 16 objective),
but runs as a **separate application and a separate database** on a **separate
subdomain**, with no navigational link either direction. See `20_EMBEDDING_WITH_ABI.md`
for the full rationale and `23_DEPLOYMENT_ARCHITECTURE.md` for process-level detail.

## Repository layout

Exactly two application folders at the top level, matching the sibling ABI project:

```
abf-fst-respondent-portal/
├── AGENTS.md
├── README.md
├── docs/
├── frontend/          # see 07_FRONTEND_ARCHITECTURE.md
└── backend/           # see 08_BACKEND_ARCHITECTURE.md
```

No `mobile/`, no standalone `api/` repo, no separate KII/document microservice, no
separate admin project. The "services" in the component diagram above are Django apps
inside the single `backend/`, exactly as ABI's "engines" are — see
`08_BACKEND_ARCHITECTURE.md`.

## Core architectural decision: this portal does not own scoring

Unlike ABI, this application has no versioned scoring engine of its own — its
"methodology" is the Main-400/Reserve-400 sample, the identifier scheme, the workflow
status machine, and the QA thresholds, all of which are config/data-driven (per
`AGENTS.md` ground rule 7) but none of which compute a bankability figure. The one
architectural parallel worth keeping in mind: exactly as ABI never lets the frontend
compute the authoritative ABI score, this portal never lets the frontend assert
eligibility, consent validity, or QA status — every one of those is a backend-computed,
API-returned fact.

## Conceptual data flow

```
MAIN-400 IMPORT → VERIFICATION → ELIGIBLE RESPONDENT IDENTIFIED
   → INVITATION TOKEN ISSUED → RESPONDENT OPENS PORTAL
   → ELIGIBILITY GATE → CONSENT → PARTICIPATION CHOICE
   → KOBO QUESTIONNAIRE (hidden identifiers + mode) → SUBMISSION
   → SCHEDULED RECONCILIATION → QA (auto + human) → QA-PASSED
   → ANALYTICAL DATASET (versioned) → DATA LOCK (30 Nov 2026)
```

KII and documentary-evidence flows run in parallel, sharing the same Sample_ID/
Master_ID identity backbone but their own consent, scheduling and coding workflows — see
`13_KII_MODULE.md` and `14_DOCUMENTARY_EVIDENCE_MODULE.md`.
