# ABF-FST Digital Respondent Portal — frontend

Next.js 15 (App Router) + TypeScript. Two experiences in one codebase: the short,
public, invitation-gated respondent flow (`/i/[token]/...`) and the internal Research
Operations Centre (`/admin/...`). See the repository root `AGENTS.md` and `docs/` for
the full specification, especially `docs/07_FRONTEND_ARCHITECTURE.md`.

## Local development

```bash
npm install
cp .env.example .env               # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

Then open `http://localhost:3000` for the neutral landing page (no public participation
entry point — this portal is invitation-only, see `docs/10_INVITATION_AND_CONSENT.md`).

## Tests

```bash
npm run test        # Vitest component tests
npm run e2e          # Playwright E2E (needs both dev servers running)
```

## Environment variables

See `.env.example` and `docs/24_ENVIRONMENT_CONFIGURATION.md`. Never commit a real
`.env`.
