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

- [x] Master_ID/Sample_ID generation matches `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`
      exactly, verified unique under a concurrent-import test. *(20 concurrent threads,
      `tests/test_sampling.py::test_master_id_generation_unique_under_concurrent_import`.)*
- [x] A locked Reserve case is structurally unreachable by every invitation-issuing code
      path — verified by an automated test, not just a manual check. *(Tested at the
      service layer and the API layer; also exercised as its own Playwright E2E
      scenario against the live deployment's code path.)*
- [x] Reserve activation always requires an authorised reason, records the authoriser,
      and writes an `AuditEvent` — verified by an automated test.
- [x] The S00–S16 workflow engine rejects invalid transitions.

## Functional completeness

- [x] A respondent can complete the invitation→eligibility→consent→Kobo-redirect flow on
      a phone-sized viewport. *(Verified live at 375px, no overflow; also the Playwright
      happy-path scenario.)*
- [x] An ineligible respondent is routed to referral, never to the questionnaire.
- [x] No questionnaire link is issued without a `GIVEN` participation consent recorded.
- [x] KII recording consent is always a separate, explicit decision from participation
      consent. *(`tests/test_kii.py` — participation consent alone never satisfies the
      recording-consent gate.)*
- [x] Sample_ID, Master_ID and administration mode arrive correctly in the Kobo hidden
      fields. **Open item**: the exact field *names* as they'll appear in a real Kobo
      form are unverified (no Kobo account provisioned) — see
      `docs/27_AGENT_EXECUTION_PLAN.md`'s Phase 3 note.
- [x] An edited Kobo submission is correctly picked up by the scheduled reconciliation
      job (not just a new submission) — verified by the dedicated test in
      `22_TESTING_STRATEGY.md`.
- [x] The QA engine correctly hard-stops and soft-flags against the thresholds in
      `15_QA_AND_DATA_QUALITY.md`, and no record reaches `QA_PASSED` without a human
      `QAEvent`.
- [x] All six dashboards render with seeded synthetic data. *(Playwright E2E, all six,
      also asserts no organisation/respondent name leaks.)*
- [x] KII and documentary-evidence modules support their full documented workflow.
      *(Status flow, transcript/coding progression, authenticity assessment, QA
      inclusion/exclusion — register + create + detail/workflow pages, verified live.)*
- [x] The reminder queue only ever dispatches the approved sequence — no ad hoc
      automated sends.
- [x] The de-identified analysis export and the full operational export both work and
      have the documented schema difference (contact fields present only in the
      operational export).

## Non-negotiables

- [x] No UI copy, API response, or export anywhere uses "approved", "loan approval",
      "credit rating", "bankability score" or "guarantee" in a respondent-facing
      context. *(Spot-checked every screen's copy; disclaimer sourced from one shared
      constant, not duplicated ad hoc.)*
- [x] No ABI score, band, or financing pathway is computed, stored, or displayed
      anywhere in this application. *(Never implemented at all, by design — no scoring
      code exists in this codebase.)*
- [x] The public/aggregate dashboards never expose an individual organisation or
      respondent name, or unbanded financial figures — verified by an automated test.
      *(Parametrised across all six dashboards, plus a full-page E2E check.)*
- [x] There is no navigational link between this application and the public ABI demo,
      in either direction (`20_EMBEDDING_WITH_ABI.md`). *(Confirmed by inspection of
      both codebases; also verified live — the deployed ABI site is unaffected and
      contains no link to this portal.)*
- [x] Repository has exactly two top-level application folders: `frontend/` and
      `backend/`.

## Quality gates

- [x] All backend automated tests pass. *(87/87, plus `ruff check .` clean.)*
- [x] All frontend component tests pass. *(8/8 Vitest, `eslint .` clean, `tsc --noEmit`
      clean.)*
- [x] All Playwright E2E scenarios pass (happy path, reserve-lock, ineligible-respondent,
      dashboard privacy, edited-submission reconciliation). *(5/5 — the "edited-
      submission reconciliation" scenario is a backend-only test per
      `docs/22_TESTING_STRATEGY.md`'s own split; the Playwright suite covers the
      browser-exercisable four plus a fifth consistency-check scenario the doc also
      lists.)*
- [ ] CI is green on the branch being deployed. **Not verified** — `.github/workflows/
      ci.yml` exists and every step mirrors a command already run and passing locally,
      but this repository has no pushed remote yet, so no real GitHub Actions run has
      occurred.
- [x] The backup/restore drill has been run and passed against the RPO/RTO targets in
      `23_DEPLOYMENT_ARCHITECTURE.md`. *(Run for real against the live production
      database, not simulated — see `docs/DEPLOYMENT.md` "Staging rehearsal".)*

## Go-live acceptance checklist (15 items, from the original blueprint's Section 20)

*(Left unchecked deliberately per the Sign-off rule below — most items are covered by
the automated test suite and this session's live deployment verification, but the
checklist itself is Phase 11's gate, to be run and signed off by the PI, not inferred
by the agent that built the system. See `docs/27_AGENT_EXECUTION_PLAN.md` Phase 10 for
exactly what was and wasn't verified live.)*

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
