# 20 — Embedding with the ABI project

This documents the shared-infrastructure decision already agreed with the sponsor: the
Digital Respondent Portal shares technology stack and production hosting with the ABI
project, but is a **separate application on a separate subdomain with no navigational
cross-links**.

## Why not fully merge into the ABI codebase

The live ABI production deployment (`agribizframework.com`) already publicly exposes a
"Start ABI Assessment" self-assessment flow that generates and displays a provisional
0–100 bankability score. That is by design for ABI's own purpose (a research
demonstration prototype, see the ABI project's own `README.md` and `18_DATA_PRIVACY.md`)
but it directly conflicts with this study's own principle (`02_PRODUCT_REQUIREMENTS.md`,
carried from the original blueprint's Section 5.6/17.3): a Main-400 respondent must
never see a provisional ABI score during primary data collection, since it could bias
subsequent responses and implies a financing determination the research has not
validated. Building the respondent portal as a sub-path of the same ABI Next.js app
would risk exactly that exposure through shared navigation, shared session state, or a
future ABI feature added without this constraint in mind.

## What is shared

- **Stack**: Next.js/TypeScript frontend + Django/PostgreSQL backend, identical major
  versions where practical (`04_TECH_STACK.md`) — chosen specifically so the same
  development skills and patterns apply to both projects.
- **Hosting**: the same Linux VPS, the same Nginx instance (one `server{}` block per
  subdomain), the same Certbot/Let's Encrypt TLS management pattern as ABI's production
  deployment — see `23_DEPLOYMENT_ARCHITECTURE.md`. This is a direct cost-containment
  decision (one server bill, not two) matching the original blueprint's own Section 16
  objective.

## What is NOT shared

- **Codebase**: two separate repositories (`abf-fst-respondent-portal/` and
  `agribusiness-bankability/`), each with its own `frontend/`/`backend/`, per
  `03_SYSTEM_ARCHITECTURE.md`.
- **Database**: a separate PostgreSQL database (`drp_db`), never the ABI project's
  `abi_db` — no cross-database foreign keys, no shared ORM models.
- **Domain/subdomain**: `research.agribizframework.com`, distinct from ABI's bare
  `agribizframework.com` — a DNS `A`/`CNAME` record plus a custom-domain/TLS entry on the
  hosting platform, with no visible or crawlable link from one to the other. Add
  `X-Robots-Tag: noindex` (or a `noindex` meta tag) on every respondent-facing route, on
  top of the invitation-token gate, as defence in depth against accidental discovery.
- **Navigation**: no link, button, or redirect from the public ABI demo to the
  respondent portal, or vice versa, in either direction, at any point.
- **Scoring**: the ABI scoring engine is never imported, called, or embedded inside this
  application — see `AGENTS.md` ground rule 3 and `25_FUTURE_ABI_ENGINE_PHASE4.md`.

## Access control

The respondent portal is not secured by obscurity (a hidden subdomain) — it is secured
by the invitation-token gate specified in `10_INVITATION_AND_CONSENT.md`, exactly as the
original blueprint's Section 20 acceptance test #1 requires ("an unauthorised/public
visitor cannot access the Main questionnaire"). The subdomain separation exists to
prevent *accidental* cross-exposure via ABI's own navigation and branding, not to serve
as the security boundary itself.

## Phase 4 reunification path

`25_FUTURE_ABI_ENGINE_PHASE4.md` describes the only point at which these two systems are
expected to connect: after the ABF-FST measurement model is empirically validated, a
data pipeline (not a shared codebase) can feed this portal's de-identified analytical
dataset into a new, validated ABI scoring run — a one-way, batch, PI-approved data
export, not a live application integration.
