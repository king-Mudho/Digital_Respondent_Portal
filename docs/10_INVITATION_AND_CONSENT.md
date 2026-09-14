# 10 — Invitation token design, eligibility gate & consent

This closes the token-design gap flagged in the September 2026 QC review: "random
high-entropy token" and "stored hashed where feasible" were directionally right but not
implementable as written. This document is the concrete specification.

## Invitation token design

- **Shape**: an opaque random token, **not** a JWT — revocability matters more than
  statelessness at this scale (a few hundred live tokens at any time), and a JWT cannot
  be un-issued short of a blocklist, which defeats the point of choosing it.
- **Length/entropy**: 32 bytes (256 bits) of CSPRNG output, base64url-encoded (43
  characters, URL-safe, no padding). Well above the ~128-bit floor the review
  recommended, at negligible cost.
- **Storage**: only a salted SHA-256 hash (`InvitationToken.token_hash`) is persisted.
  The raw token exists only in the URL sent to the respondent and briefly in server
  memory during issuance and validation — it is never logged, never stored in
  `AuditEvent.metadata`, and never appears in application logs (scrub in the logging
  middleware).
- **Transport**: `https://research.agribizframework.com/i/<token>` sent via WhatsApp,
  email, SMS, or rendered as a QR code; a manual invitation-code entry path (a shorter,
  separately-issued 8-character alphanumeric code, also hashed) exists for respondents
  who receive the code by telephone or printed letter, per the blueprint's Section 5.2.
- **Expiry**: default 14 days from `issued_at`, extendable by an RA via
  `POST /api/v1/invitations/` (which supersedes the prior token rather than mutating
  it — see below). Expiry duration is a `QARuleThreshold`-style config value
  (`invitation_token_expiry_days`), not a hardcoded constant, so the PI can tune it
  without a redeploy.
- **Single-valid-token rule**: a `SampleCase` may have multiple `InvitationToken` rows
  over time (full audit history — resends, expiries, revocations), but only the most
  recently issued, non-expired, non-revoked one is valid. Issuing a new token
  automatically expires any still-open prior token for the same case.
- **Revocation**: an RA can revoke a token immediately (`POST
  /invitations/{id}/revoke/`), e.g. on a confirmed wrong-number or a respondent request —
  this writes `revoked_at`/`revoked_reason` and an `AuditEvent`.
- **Rate limiting**: validation attempts are throttled per token (to blunt guessing of
  the manual entry code) and per source IP, using DRF's throttling classes.
- **What the token is not**: device-bound. The original blueprint correctly rejects
  device-only restriction as the sole authentication mechanism, since executives may
  switch devices — the token itself, not the device, is the credential.

## Eligibility gate

The portal confirms the organisation and determines whether the respondent is a
knowledgeable organisational respondent, from the fixed role-category list in
`02_PRODUCT_REQUIREMENTS.md`/`05_DATABASE_ARCHITECTURE.md` (`Respondent.role_category`).

If ineligible, the questionnaire never opens. Instead the flow offers a
referral/nominating action so the correct respondent can be identified, without the
gatekeeper being recorded as a completed respondent — `Respondent.is_eligible` stays
`False` and a new `Respondent` row is created for the nominated person once contact is
re-established.

## Consent module

- Displays the approved, versioned Participant Information Sheet in a readable mobile
  format.
- Requires affirmative consent (explicit action, not a pre-checked box) before the
  questionnaire opens.
- Stores `ConsentRecord` with `sample_case`, `respondent`, `consent_type`,
  `information_sheet_version`, `decision`, `method`, `timestamp` — see
  `05_DATABASE_ARCHITECTURE.md`.
- Provides a downloadable/viewable copy of the participant information where permitted.
- KII recording consent is always a **separate** `ConsentRecord` row
  (`consent_type = KII_RECORDING`), captured at or just before the interview, never
  inferred from participation consent — enforced at the service layer, not left to UI
  convention (`AGENTS.md` ground rule 6).
- Withdrawal is a first-class action: a later `ConsentRecord` with
  `decision = WITHDRAWN` supersedes the prior `GIVEN` row; withdrawal triggers the
  data-handling procedure in `18_DATA_PRIVACY_AND_COMPLIANCE.md`.

## Participation choices

After consent, the respondent chooses: complete the questionnaire online now; schedule
a telephone-assisted questionnaire; request WhatsApp-assisted participation; request a
researcher to contact them; or request an alternative accessible mode where
connectivity or digital literacy is a barrier. Each choice writes the corresponding
`Appointment` or `ContactEvent` and sets the appropriate `administration_mode` for the
eventual `QUANSubmission` — see `11_KOBOTOOLBOX_INTEGRATION.md`.

## Completion

After Kobo submission, the portal shows a neutral confirmation and study contact
details. No provisional ABI score, band, or financing recommendation is ever shown — see
`18_DATA_PRIVACY_AND_COMPLIANCE.md` and `20_EMBEDDING_WITH_ABI.md`.

## Implementation notes (2026-09-14)

- **Supersession covers every pre-submission status.** Issuing a new invitation expires
  prior tokens at GENERATED, SENT, OPENED, ELIGIBILITY_PASSED, CONSENTED and
  SURVEY_STARTED. Before, only the first three were expired, so a respondent who had
  consented kept a working link beside the new one (found by `golive_preflight`).
- **Withdrawal is operable.** Coordinators record it on the case page
  (`consent.withdrawal.record_withdrawal`): a WITHDRAWN participation `ConsentRecord`
  (method: verbal or written), every open invitation revoked (which also stops reminders),
  S12 where the workflow allows, and respondent phone, WhatsApp, email and gatekeeper
  contact erased. Submitted questionnaire data is not deleted — the analysis export gains
  `consent_withdrawn` so it can be excluded — because what happens to it is the ethics
  protocol's decision. Audited as `consent.withdrawal_processed`.
