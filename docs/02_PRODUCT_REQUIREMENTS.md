# 02 — Product requirements

## Functional requirements

### Sample & identity
- FR-1: Import the approved Main-400 and locked Reserve-400 registers with their frozen
  Master_ID/Sample_ID scheme (`09_IDENTIFIER_AND_SAMPLING_CONTROL.md`).
- FR-2: Enforce that a `RESERVE` case cannot be invited while its status is `LOCKED`, at
  the database/service layer, not only in the UI.

### Invitation, eligibility & consent
- FR-3: Generate a high-entropy, single-valid, expiring invitation token per Sample_ID
  (`10_INVITATION_AND_CONSENT.md`), deliverable via WhatsApp, email, SMS, printed
  code, or QR.
- FR-4: Validate a token without exposing unnecessary sampling information (no visible
  Sample_ID, stratum, or Reserve status to the respondent).
- FR-5: Confirm organisational and respondent eligibility before any questionnaire
  opens; route an ineligible respondent to a referral flow rather than treating them as
  a completed respondent.
- FR-6: Capture versioned, timestamped electronic consent, with KII recording consent
  captured as a separate, later decision — never implied by participation consent.

### QUAN via Kobo
- FR-7: Launch the KoboToolbox questionnaire with controlled hidden fields (Master_ID,
  Sample_ID, Invitation_Wave, Administration_Mode, Respondent_Role_Category,
  Consent_Status/Version, RA_ID, timestamps, Portal_Token_ID) — see
  `11_KOBOTOOLBOX_INTEGRATION.md`.
- FR-8: Reconcile Kobo submission status into the portal on a schedule (not
  webhook-only — see `11_KOBOTOOLBOX_INTEGRATION.md` for why), including submissions
  that were later edited in Kobo.
- FR-9: Run automated + human QA against numerically defined thresholds
  (`15_QA_AND_DATA_QUALITY.md`) and record an accept/query/reject decision per record.

### Contact, appointments & messaging
- FR-10: Maintain a contact/appointment register per Sample_ID with a full contact-
  attempt audit trail and a controlled reminder queue (never auto-sending outside the
  approved sequence) — see `12_CONTACT_CRM_AND_MESSAGING.md`.
- FR-11: Send invitations/reminders via WhatsApp Business Platform pre-approved utility
  templates, with email/SMS/telephone as fallback channels.

### KII & documentary evidence
- FR-12: Support KII scheduling, consent (participation + separate recording consent),
  transcript/recording reference tracking, and thematic coding status
  (`13_KII_MODULE.md`).
- FR-13: Support a provenance-controlled documentary-evidence repository with construct
  tagging and QA/inclusion status (`14_DOCUMENTARY_EVIDENCE_MODULE.md`).

### Dashboards & operations
- FR-14: Provide executive, sampling, contact, QUAN-QA, KII/document and cost
  dashboards (`16_DASHBOARDS_AND_REPORTING.md`).
- FR-15: Provide AI Field Coordinator decision-support flags (duplicates, reserve
  violations, stratum shortfalls, QA issues, transcript backlog, burn rate) with human
  approval required for every consequential action (`17_AI_FIELD_COORDINATOR.md`).

### Accounts & audit
- FR-16: Role-based internal accounts (PI/Admin, Supervisor read-only, Field
  Coordinator, Contact RA, QUAN RA, KII RA, Documentary RA, Analyst). Public respondents
  never need an account.
- FR-17: Record an `AuditEvent` for every sampling, consent, response-acceptance,
  reserve-activation and data-lock action.

## Non-functional requirements

- NFR-1: **Responsive**, mobile-first, from a single Next.js codebase; must work well on
  low-cost Android phones and variable connectivity.
- NFR-2: The respondent-facing flow degrades gracefully offline where feasible (draft
  persistence for in-progress forms up to the Kobo handoff — the questionnaire itself is
  Kobo's own offline-capable client, not this portal's concern).
- NFR-3: Backend is the **single source of truth** for eligibility, consent state, token
  validity, workflow status and QA decisions; the frontend never asserts these itself.
- NFR-4: QA thresholds, token expiry, reminder cadence and RPO/RTO targets are
  **database/config-driven and versioned**, never hardcoded — mirrors the ABI project's
  `FrameworkVersion` principle.
- NFR-5: Respondent financial or personally identifying information is **never** exposed
  on any aggregate/public dashboard or export — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- NFR-6: HTTPS everywhere in deployment; audit logging for every sensitive action.
- NFR-7: Reasonable accessibility — labelled controls, sufficient colour contrast,
  keyboard-navigable flows.
- NFR-8: The system must be operable by a Field Coordinator with no engineering
  background — dashboards and QA queues are the primary interface for daily operations.

## Out of scope for v1.0

Do **not** build any of the following in this phase — explicitly deferred to
`25_FUTURE_ABI_ENGINE_PHASE4.md` or beyond:

- Public ABI self-assessment or any ABI score/band shown to a respondent.
- Automated bankability scoring, lender dashboards, credit recommendations.
- Enterprise benchmarking or AI-generated financing advice.
- Native Android/iOS application (a responsive web app is sufficient).
- Fully automated (human-unsupervised) messaging beyond the approved reminder sequence.
- Celery/Redis async processing, unless a specific v1.0 feature genuinely needs it
  (matches the sibling ABI project's own stack discipline — see `04_TECH_STACK.md`).

## Acceptance

Requirements above map to `28_DEFINITION_OF_DONE.md` and the 15-item go-live checklist
there.
