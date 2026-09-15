# 28 — Definition of done

The build is complete only when every item below is checked, on a fresh checkout, with
synthetic seed data loaded — and the 15-item go-live checklist passes before the first
real Main-400 invitation is issued.

> **A checked box is a claim, and claims here have been wrong.** During the September 2026
> audit pass, "an ineligible respondent is routed to referral, never to the questionnaire"
> was ticked while no such control existed in the code: the frontend declined to route
> there, the docstring said it was enforced, and the test that appeared to cover it passed
> for an unrelated reason. Before ticking an item, name the test or the enforcement point,
> and satisfy yourself the test still fails when the control is removed. An unchecked box
> is a known gap; a wrongly checked one is why nobody looks.

## Compliance gate (blocks go-live, not early development)

- [x] The POTRAZ/Data Protection Officer position is resolved in writing
      (`18_DATA_PRIVACY_AND_COMPLIANCE.md`). *(2026-09-12: covered by CUT's Research
      Ethics Clearance and the study's institutional research governance.)*
- [ ] WhatsApp Business Platform utility-category templates are Meta-approved
      (`12_CONTACT_CRM_AND_MESSAGING.md`). *(No longer blocks fieldwork as of 2026-09-14:
      invitations and reminders can be sent by hand from the case page and the Follow-ups
      screen. It blocks only automated sending. The invitation and reminder wording still
      needs PI approval — `31` Part A.)*
- [x] **The Participant Information Sheet wording is approved by the PI and the CUT
      Research Ethics office.** *(2026-09-15, PI's written statement in the build session:
      the study is carried out under his CUT student research clearance, which covers data
      collection, ethics and POTRAZ, and he approves v1.3 — the live version, which
      includes the PROIT disclosure. Recorded as the PI's statement; no separate ethics
      office signature is held in this repository.)*
- [x] **The QUAN QA rule thresholds are confirmed by the PI.** *(2026-09-15, PI-approved
      as configured: 5–90 minute plausible duration, 24-hour duplicate window, 65 required
      fields from the live form, 70% mode-imbalance alert (now evaluated on Reports). Every
      `QARuleThreshold.set_by` is the PI; audit event `qa.thresholds_approved`. The
      invitation and reminder wording was approved at the same time
      (`messaging.wording_approved`).)*

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
      *(**Was wrongly checked until 2026-09-13.** Only the frontend routing and a
      docstring backed this; `/api/v1/consent/` is `AllowAny`, so anyone screened out
      could POST consent directly and be handed a Kobo URL. Now enforced in
      `kobo.services.build_redirect_url()` via `contacts.services.has_passed_eligibility`,
      with tests that give consent first — which is what a bypass looks like — and an
      E2E spec on a case with no prior history. No invitation had been issued when this
      was found, so no real respondent was affected.)*
- [x] No questionnaire link is issued without a `GIVEN` participation consent recorded.
      *(Single enforcement point, `kobo.services.build_redirect_url()`; also covers the
      eligibility half above.)*
- [x] No appointment can be requested before participation consent is given.
      *(PI decision, 2026-09-13: an appointment request is a researcher-assisted route
      into the study, not a separate enquiry. `403 consent_required`; a declined consent
      is refused too.)*
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
- [x] Every register screen is usable at real data volumes. *(Added 2026-09-13: page size
      is 20 against 400 Main + 400 Reserve + 90 KII + 100 documents, and no register had
      a paging control, so every row past the first twenty was unreachable from the UI.
      All registers now paginate and most carry a `?search=` box; `KIIRecord` and
      `DocumentRecord` querysets are explicitly ordered, since unordered pagination made
      page boundaries arbitrary.)*
- [x] Each role sees only its own modules, and lands on a screen it can actually open.
      *(Added 2026-09-13: `backend/api/navigation.py` is the single source of truth,
      served by `GET /api/v1/auth/me/`. Previously all 14 links showed to every role and
      everyone landed on `/admin/dashboard`, which four of the eight roles are refused.
      Covered by `tests/test_role_navigation.py` and
      `e2e/role-scoped-navigation.spec.ts`.)*
- [x] PROIT pre-profiles can be built, reviewed and locked, and a respondent can confirm
      or correct each fact without it ever pre-filling a frozen scale item.
      *(`30_PROIT_MODULE.md`. Respondent-facing PROIT is gated on
      `PROIT_ENABLED_FOR_RESPONDENTS`, enabled on the PI's documented risk acceptance —
      which is a risk acceptance, not an ethics or change-control clearance.)*

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

- [x] All backend automated tests pass. *(260/260 as at 2026-09-13, plus `ruff check .`
      clean.)*
- [x] All frontend component tests pass. *(8/8 Vitest, `eslint .` clean, `tsc --noEmit`
      clean.)*
- [x] All Playwright E2E scenarios pass (happy path, reserve-lock, ineligible-respondent,
      dashboard privacy, edited-submission reconciliation). *(26 specs, 25 run and 1
      intentionally skipped, as at 2026-09-13. The "edited-submission reconciliation"
      scenario is a backend-only test per `docs/22_TESTING_STRATEGY.md`'s own split. Also
      covers role-scoped navigation per role and the respondent flow's failure branches.)*
- [x] A test that guards a rule actually fails when the rule is removed. *(Added
      2026-09-13 after three tests were found passing for the wrong reason: two gate tests
      against a shared seed case that had accumulated consent and eligible respondents
      across runs, and an ordering test whose fixtures happened to be inserted in sorted
      order. Verified by removing each control and watching the test go red.)*
- [ ] CI is green on the branch being deployed. **Not verified** — `.github/workflows/
      ci.yml` exists and every step mirrors a command already run and passing locally,
      but this repository has no pushed remote yet, so no real GitHub Actions run has
      occurred.
- [x] The backup/restore drill has been run and passed against the RPO/RTO targets in
      `23_DEPLOYMENT_ARCHITECTURE.md`. *(Run for real against the live production
      database, not simulated — see `docs/DEPLOYMENT.md` "Staging rehearsal".)*
- [x] **A backup mechanism exists that can actually meet the ≤ 4-hour fieldwork RPO.**
      *(Found broken and fixed 2026-09-13. The drill above had passed, but the drill is
      not the mechanism: `deploy.sh` tested `backup.sh` with `-x`, the executable bit does
      not survive the code-transfer route, so every deploy silently skipped the backup
      behind a one-line warning — and the newest restore point predated the register
      import by a day. Now: the test is `-f` and invokes through `bash`, a failed backup
      aborts the deploy instead of warning, and `drp-backup.timer` runs `backup.sh` every
      four hours on the clock with `Persistent=true` so a run missed during an outage
      fires at next boot. Verified by triggering `drp-backup.service` manually — result
      `success`, 121K written, ownership handed back to the app user — and by extracting
      the backup and counting rows: 800 organisations, 800 sample cases, 90 KII, 100
      documents, 128 respondents.)*
- [ ] **The repository has an offsite copy and CI has run at least once.** *(Open. All
      commits exist only on the PI's laptop — no remote, so the build history has a single
      point of failure, and `.github/workflows/ci.yml` has never executed. Scanned for
      safety ahead of a push: no credentials, keys or `.env` files are tracked, and the
      only personal data is the PI's own study contact details, which are in the
      respondent-facing materials deliberately. The workflow now triggers on `master` as
      well as `main` — it listed only `main` while the branch is `master`, so the first
      push would have run no checks and left this item silently unverifiable. The PI will
      push to GitHub.)*

## Go-live acceptance checklist (15 items, from the original blueprint's Section 20)

*(Left unchecked deliberately per the Sign-off rule below — most items are covered by
the automated test suite and this session's live deployment verification, but the
checklist itself is Phase 11's gate, to be run and signed off by the PI, not inferred
by the agent that built the system. See `docs/27_AGENT_EXECUTION_PLAN.md` Phase 10 for
exactly what was and wasn't verified live.)*

*(Two of these — the ineligible-respondent route and role-based permissions — describe
controls that did not fully exist when this checklist was written, and were built during
the September 2026 audit. Notes below say what now backs them. That is context for the
PI's run-through, not a substitute for it.)*

*(**Engineering pre-flight, 2026-09-14: 15/15 passed against production** —
`manage.py golive_preflight`, which exercises items 1–11 and 14 through the real API
inside a rolled-back transaction and proves row counts unchanged afterwards. Items 12 and
13 are evidenced below. The run found and fixed one defect (item 7). Boxes stay unticked
for the PI's own run-through.)*

- [ ] An unauthorised/public visitor cannot access the Main questionnaire. — *pre-flight
      PASS: bogus links refused; the questionnaire's public web link cannot be used to
      submit for a guessed case (login-free submissions must carry the portal's per-case
      signature, added 2026-09-14).*
- [ ] A valid Main invitation opens the correct organisation/case without revealing
      unnecessary data. — *pre-flight PASS (payload: confirmation name and status only).*
- [ ] A locked Reserve cannot receive an invitation. — *pre-flight PASS (HTTP 403, no token).*
- [ ] An ineligible respondent is routed to referral rather than questionnaire
      completion. — *now enforced server-side in `kobo.services.build_redirect_url()`;
      until 2026-09-13 only the frontend routing prevented it. Pre-flight PASS
      (403 `eligibility_required` even with consent given).*
- [ ] No questionnaire starts without the required consent state. — *pre-flight PASS
      (declined → 403 `consent_required`).*
- [ ] Sample_ID and administration mode arrive correctly in Kobo. — *proven live with a
      synthetic submission on 2026-09-14 (matched to its case, mode 01), and pre-flight PASS.*
- [ ] Duplicate or reused tokens are handled according to `10_INVITATION_AND_CONSENT.md`.
      — *pre-flight FAILED first: a link that had reached consent stayed live after a
      reissue. Fixed and deployed; now PASS.*
- [ ] A Kobo submission (new or edited) updates the portal and enters QA. — *new: proven
      live (webhook → sync → QA queue in about a second). Edited: covered by tests after
      switching to `meta/rootUuid`, since an edit changes `_uuid`.*
- [ ] Contact data is not present in the de-identified analytical export. — *pre-flight PASS.*
- [ ] Role-based permissions prevent RAs from seeing records outside their duties.
      — *pre-flight PASS (Contact RA 403 on audit, export, QA, KII); per-role navigation
      E2E passes for all eight roles.*
      — *worth exercising per role rather than in aggregate: sign in as each of the eight
      and confirm the navigation bar matches `18_DATA_PRIVACY_AND_COMPLIANCE.md`'s access
      matrix. The three RA roles previously shared one permission class, so a KII RA could
      edit documentary evidence and a Documentary RA could take QUAN QA decisions.*
- [ ] Reserve activation creates an audit event with reason and authoriser. — *pre-flight PASS.*
- [ ] Backup and restore are tested. — *4-hourly timer succeeding (last run checked
      2026-09-14 16:00 UTC); staging is rebuilt from the latest backup on every deploy,
      which is a restore test each time. Backups are still only on the same server — see
      `33_GO_LIVE_READINESS.md`.*
- [ ] Mobile pages work on typical Android screens and poor/variable connectivity. —
      *E2E `respondent-poor-connectivity.spec.ts`: full journey on a 360×740 screen, 4×
      CPU slowdown and a slow-3G link (≈66 s on the unminified dev build); a slow tap
      cannot submit twice.*
- [ ] Withdrawal and consent-revocation procedures are operationally testable. — *there
      was no way to record a withdrawal until 2026-09-14. Built, E2E-tested
      (`admin-withdrawal.spec.ts`) and pre-flight PASS.*
- [x] The POTRAZ/data-protection position is resolved and reflected in the deployed
      access-control configuration. *(2026-09-12: see `18_DATA_PRIVACY_AND_
      COMPLIANCE.md` — covered by CUT's Research Ethics Clearance.)*

## Data state at go-live

The three approved registers were imported in September 2026 and the production database
holds real, identifying study data: 400 Main and 400 Reserve sample cases across 800 named
organisations, 90 KII records, 100 documentary-evidence records, all 400 Main cases paired
to their matched Reserve.

What has **not** happened: no invitation has been issued, no consent recorded, no
appointment booked, no submission received. Verifying that before go-live is a useful
sanity check that no test traffic has leaked into the record:

```bash
# expect 0, 0, 0, 0 and 400 / 400
python manage.py shell -c "
from apps.invitations.models import InvitationToken
from apps.consent.models import ConsentRecord
from apps.contacts.models import Appointment
from apps.kobo.models import QUANSubmission
from apps.sampling.models import SampleCase, SampleType
print(InvitationToken.objects.count(), ConsentRecord.objects.count(),
      Appointment.objects.count(), QUANSubmission.objects.count(),
      SampleCase.objects.filter(sample_type=SampleType.MAIN).count(),
      SampleCase.objects.filter(sample_type=SampleType.RESERVE).count())
"
```

The audit log will not be empty, and should not be: it carries a small number of
deployment-verification entries from 13 September 2026, itemised in
`27_AGENT_EXECUTION_PLAN.md`'s open questions so they are not mistaken at review for real
respondent activity.

## Sign-off

Only once every box above is checked — the compliance gate and the 15-item go-live
checklist included — should the agent report the build ready for the PI's go-live
decision, referencing this file explicitly. The PI, not the agent, makes the final
go-live call.
