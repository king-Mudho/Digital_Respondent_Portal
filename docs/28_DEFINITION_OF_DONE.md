# 28 — Definition of done

The build is complete only when every item below is checked, on a fresh checkout, with
synthetic seed data loaded — and the 15-item go-live checklist passes before the first
real Main-400 invitation is issued.

## Compliance gate (blocks go-live, not early development)

- [ ] The POTRAZ/Data Protection Officer position is resolved in writing
      (`18_DATA_PRIVACY_AND_COMPLIANCE.md`).
- [ ] WhatsApp Business Platform utility-category templates are Meta-approved
      (`12_CONTACT_CRM_AND_MESSAGING.md`).

## Sample & identifier integrity

- [ ] Master_ID/Sample_ID generation matches `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`
      exactly, verified unique under a concurrent-import test.
- [ ] A locked Reserve case is structurally unreachable by every invitation-issuing code
      path — verified by an automated test, not just a manual check.
- [ ] Reserve activation always requires an authorised reason, records the authoriser,
      and writes an `AuditEvent` — verified by an automated test.
- [ ] The S00–S16 workflow engine rejects invalid transitions.

## Functional completeness

- [ ] A respondent can complete the invitation→eligibility→consent→Kobo-redirect flow on
      a phone-sized viewport.
- [ ] An ineligible respondent is routed to referral, never to the questionnaire.
- [ ] No questionnaire link is issued without a `GIVEN` participation consent recorded.
- [ ] KII recording consent is always a separate, explicit decision from participation
      consent.
- [ ] Sample_ID, Master_ID and administration mode arrive correctly in the Kobo hidden
      fields.
- [ ] An edited Kobo submission is correctly picked up by the scheduled reconciliation
      job (not just a new submission) — verified by the dedicated test in
      `22_TESTING_STRATEGY.md`.
- [ ] The QA engine correctly hard-stops and soft-flags against the thresholds in
      `15_QA_AND_DATA_QUALITY.md`, and no record reaches `QA_PASSED` without a human
      `QAEvent`.
- [ ] All six dashboards render with seeded synthetic data.
- [ ] KII and documentary-evidence modules support their full documented workflow.
- [ ] The reminder queue only ever dispatches the approved sequence — no ad hoc
      automated sends.
- [ ] The de-identified analysis export and the full operational export both work and
      have the documented schema difference (contact fields present only in the
      operational export).

## Non-negotiables

- [ ] No UI copy, API response, or export anywhere uses "approved", "loan approval",
      "credit rating", "bankability score" or "guarantee" in a respondent-facing
      context.
- [ ] No ABI score, band, or financing pathway is computed, stored, or displayed
      anywhere in this application.
- [ ] The public/aggregate dashboards never expose an individual organisation or
      respondent name, or unbanded financial figures — verified by an automated test.
- [ ] There is no navigational link between this application and the public ABI demo,
      in either direction (`20_EMBEDDING_WITH_ABI.md`).
- [ ] Repository has exactly two top-level application folders: `frontend/` and
      `backend/`.

## Quality gates

- [ ] All backend automated tests pass.
- [ ] All frontend component tests pass.
- [ ] All Playwright E2E scenarios pass (happy path, reserve-lock, ineligible-respondent,
      dashboard privacy, edited-submission reconciliation).
- [ ] CI is green on the branch being deployed.
- [ ] The backup/restore drill has been run and passed against the RPO/RTO targets in
      `23_DEPLOYMENT_ARCHITECTURE.md`.

## Go-live acceptance checklist (15 items, from the original blueprint's Section 20)

- [ ] An unauthorised/public visitor cannot access the Main questionnaire.
- [ ] A valid Main invitation opens the correct organisation/case without revealing
      unnecessary data.
- [ ] A locked Reserve cannot receive an invitation.
- [ ] An ineligible respondent is routed to referral rather than questionnaire
      completion.
- [ ] No questionnaire starts without the required consent state.
- [ ] Sample_ID and administration mode arrive correctly in Kobo.
- [ ] Duplicate or reused tokens are handled according to `10_INVITATION_AND_CONSENT.md`.
- [ ] A Kobo submission (new or edited) updates the portal and enters QA.
- [ ] Contact data is not present in the de-identified analytical export.
- [ ] Role-based permissions prevent RAs from seeing records outside their duties.
- [ ] Reserve activation creates an audit event with reason and authoriser.
- [ ] Backup and restore are tested.
- [ ] Mobile pages work on typical Android screens and poor/variable connectivity.
- [ ] Withdrawal and consent-revocation procedures are operationally testable.
- [ ] The POTRAZ/data-protection position is resolved and reflected in the deployed
      access-control configuration.

## Sign-off

Only once every box above is checked — the compliance gate and the 15-item go-live
checklist included — should the agent report the build ready for the PI's go-live
decision, referencing this file explicitly. The PI, not the agent, makes the final
go-live call.
