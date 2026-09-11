# 07 — Frontend architecture

Next.js + TypeScript, App Router. Two distinct experiences in one codebase: the short,
public, invitation-gated **respondent flow** (R01–R10) and the internal, authenticated
**Research Operations Centre** (A01–A12). The frontend never asserts eligibility,
consent validity or QA status itself — every gate is a backend API response it renders.

## Directory structure

```
frontend/
├── app/
│   ├── page.tsx                  # Neutral landing — no public "start" CTA (invitation-only)
│   ├── i/[token]/                # Respondent flow, keyed by invitation token
│   │   ├── page.tsx              # R02 Invitation validation
│   │   ├── confirm/               # R03 Organisation confirmation
│   │   ├── eligibility/           # R04 Eligibility gate
│   │   ├── information/           # R05 Participant information
│   │   ├── consent/               # R06 Electronic consent
│   │   ├── choice/                # R07 Participation choice
│   │   ├── kobo-redirect/         # R08 Kobo questionnaire redirect
│   │   ├── appointment/           # R09 Appointment request
│   │   └── done/                  # R10 Completion / thank you
│   ├── admin/                     # Research Operations Centre (A01-A12), internal login required
│   │   ├── login/                 # A01
│   │   ├── dashboard/             # A02 Executive dashboard
│   │   ├── sample/                # A03 Main-400 register
│   │   ├── sample/[sampleId]/     # A04 Case detail / contact timeline
│   │   ├── appointments/          # A05 Appointment queue
│   │   ├── qa/                    # A06 QUAN QA queue
│   │   ├── kii/                   # A07 KII register
│   │   ├── documents/             # A08 Documentary corpus
│   │   ├── reserve/                # A09 Reserve activation
│   │   ├── cost/                   # A10 Cost dashboard
│   │   ├── audit/                  # A11 Audit log
│   │   └── export/                 # A12 Data-lock export
│   └── api/                       # Next.js route handlers (auth cookie relay only)
├── components/
│   ├── ui/                        # shadcn/ui primitives
│   ├── respondent/                 # Invitation, eligibility, consent, choice screens
│   ├── admin/                      # Register tables, case detail, QA queue rows
│   ├── dashboard/                  # Stat cards, filters
│   └── charts/                     # Recharts wrappers
├── lib/
│   ├── api/                        # Typed fetch client for /api/v1
│   ├── auth/                       # JWT storage/refresh (internal users only)
│   ├── validation/                  # Zod schemas mirroring backend serializers
│   └── utils/
├── hooks/
├── types/                          # Shared TS types mirrored from OpenAPI schema
├── config/                         # Env-driven constants (domain, API base URL)
├── public/
├── styles/
├── tests/
├── package.json
├── tsconfig.json
├── next.config.ts
└── README.md
```

## Routing → screens mapping

See `10_INVITATION_AND_CONSENT.md` for the respondent flow's gating logic and
`16_DASHBOARDS_AND_REPORTING.md` for dashboard layouts. Route summary:

| Route | Screen |
|---|---|
| `/` | Neutral landing, study identity, no public participation entry point |
| `/i/[token]` | R02 Invitation validation |
| `/i/[token]/confirm` | R03 Organisation confirmation |
| `/i/[token]/eligibility` | R04 Eligibility gate (with referral path if ineligible) |
| `/i/[token]/information` | R05 Participant information |
| `/i/[token]/consent` | R06 Electronic consent |
| `/i/[token]/choice` | R07 Participation choice (self, phone-assisted, WhatsApp-assisted, request-contact) |
| `/i/[token]/kobo-redirect` | R08 Kobo questionnaire redirect |
| `/i/[token]/appointment` | R09 Appointment request |
| `/i/[token]/done` | R10 Completion / thank you (neutral — no score, see `18_DATA_PRIVACY_AND_COMPLIANCE.md`) |
| `/admin/*` | A01–A12, internal Research Operations Centre |

## State management

- **Server state** (case detail, dashboards, QA queue): TanStack Query, cache
  invalidated on the relevant mutation (QA decision, reserve activation, consent
  submit).
- **Respondent-flow-in-progress state** (current step within one token's session):
  Zustand, scoped to the token, not persisted beyond the browser tab — there is no
  multi-day draft to protect here, unlike ABI's 24-question wizard, because this flow is
  short and each step is already durably recorded server-side as it completes.
- Forms via React Hook Form + Zod; Zod schemas mirror backend serializer constraints in
  `lib/validation/`.

## Token handling

The invitation token lives in the URL path (`/i/[token]/...`), never in a cookie or
localStorage keyed globally — each screen re-validates the token server-side against
`InvitationToken.token_hash` rather than trusting client-held state. See
`10_INVITATION_AND_CONSENT.md`.

## Design tokens

Legitimacy-first, university-research visual identity (never resembling a commercial
loan-application flow) — defined in `21_UI_UX_GUIDELINES.md` and implemented as Tailwind
config + CSS variables, matching ABI's approach of not inventing ad hoc colours in
components.
