# 33 — Go-live readiness (14 September 2026)

The result of a full end-to-end audit of the deployed system and its KoboToolbox
connection, what it fixed, and what still has to happen before the first live Main-400
invitation. Evidence for each checklist item sits against it in
`28_DEFINITION_OF_DONE.md`.

**Position: engineering-ready, not yet cleared to go live.** Every technical item on the
go-live checklist has been exercised against production and passes. What remains is
approvals, contact data, credentials, and a user-acceptance run — none of which the
software can do for the team.

## What was verified

| Area | Evidence |
|---|---|
| Go-live checklist items 1–11, 14 | `manage.py golive_preflight` on production: **15/15**, all writes rolled back, row counts unchanged |
| Portal ↔ KoboToolbox | A synthetic submission went portal → questionnaire → KoboToolbox (no login) → webhook → portal → QA queue in about a second; test records removed afterwards |
| Mobile and poor connectivity | Full respondent journey on a 360×740 screen, 4× CPU slowdown, slow-3G link; a slow tap cannot submit twice |
| Automated suites | Backend 339 passed; E2E 34 passed, 1 deliberately skipped (WhatsApp Business Platform) |
| Production health | 7 services active; 4-hourly backups succeeding; certificate valid to 10 Dec 2026; no errors since deploy; HSTS on pages and API |

## What the audit found and fixed

In rough order of consequence. Each has a test that fails without the fix.

1. **Research answers were publicly downloadable.** nginx served `/media/`, where full Kobo
   payloads were written. Now stored privately, `/media/` returns 404, payload files are
   backed up (they never were).
2. **Anyone with the questionnaire's public link could submit for a guessed case.** Portal
   links now carry a per-case signature; login-free submissions without one are set aside.
3. **Cases could be replaced by reserves without anyone following up.** S13 Nonresponse was
   set on day 8 by the calendar while every reminder silently failed. It now needs every
   reminder actually sent.
4. **No reminder could ever reach a respondent.** They failed into rows no screen showed.
   The new Follow-ups screen sends them by hand through WhatsApp and records who sent them.
5. **Staff could not record a phone number.** Only 51 of 400 Main cases had one, with no
   way to add more. The case page now has a contact-details panel.
6. **Withdrawal could not be recorded at all.** Now one action: consent withdrawn,
   invitations revoked, reminders stop, contact details erased, export flagged.
7. **A reissued invitation left the old link working** once the respondent had consented.
8. **Case status never moved past "Invitation sent".** It now follows the respondent to
   QA passed. Coordinators can move cases through verification in bulk.
9. **Kobo edits would have duplicated submissions** (an edit changes `_uuid`), **times were
   two hours off**, and **duration was never recorded**, so the duration QA rules could not
   fire. All fixed; required-field QA is now active with 65 fields from the live form.

## Before the first live invitation — must happen

| # | Item | Owner | How |
|---|---|---|---|
| 1 | ~~Approve the Participant Information Sheet v1.3~~ | PI | **Done 2026-09-15** — PI approval; covered by his CUT research clearance (ethics, POTRAZ) |
| 2 | ~~Approve the QA thresholds and the invitation and reminder texts~~ | PI | **Done 2026-09-15** |
| 3 | Collect respondent contact details | Field Coordinator + Contact RAs | Case page → *Respondents and contact details*; 349 Main cases have no number |
| 4 | ~~Assign cases to Contact RAs~~ | PI | **Done 2026-09-15** — all 400 Main cases assigned to the `contact_ra` account on the PI's instruction. Next: named accounts from `docs/templates/ABF-FST_Staff_Accounts_Template.xlsx` via `create_staff_accounts --assign-cases`, then **Reassign cases** on the register |
| 5 | ~~Move cases through verification to S03~~ | PI | **Done 2026-09-15** — all 400 at S03, each transition audited, on the PI's instruction |
| 6 | Rotate the KoboToolbox password and API token | PI | Then `sudo bash /srv/agribiz-drp/deploy/configure-kobo.sh` with the new token |
| 7 | Finish offsite backups: sign in to Google Drive once, then store the encryption key in a password manager | PI | Built and tested; run the one command in `23` "Offsite backups". Until then backups live only on the same VPS |
| 8 | Push to GitHub and let CI run once | PI | `.github/workflows/ci.yml` has never run |
| 9 | User-acceptance run | PI, Field Coordinator, one RA | Invite one friendly test respondent end to end on a real phone |
| 10 | ~~Decide the open instrument questions~~ | PI | **Done 2026-09-15** (recorded in System Manual 9.3; KII form redeployed):<br>• Section 10 stays shown to everyone, optional, as frozen.<br>• Documents "Exclude" keeps skipping C–L.<br>• KII category list confirmed identical to the source; Executive Short Form wording and K-codes restored.<br>• Withdrawn participants' submitted answers are kept but never analysed. |

## Should happen soon — does not block

- **WhatsApp Business Platform** (Meta account, verified number, approved utility
  templates) to send reminders automatically instead of by hand.
- **PROIT** — confirmed by the PI on 2026-09-15 as covered by his CUT research clearance (`30`).
- **Server memory**: 956 MB shared with the ABI site, running on swap. Move to 2 GB before
  fieldwork peaks.
- **QA engine gaps**: `mode_imbalance_alert_ratio` is configured but not implemented;
  logic-violation rules are empty.
- **API documentation**: about 40 views lack schema annotations (log noise only).
- **ABI site** (separate project): its nginx config also serves `/media/` publicly — worth
  checking there.
- **ResearchOS backlog** (`32`): Kobo duplicate quarantine, case timeline, cost attribution,
  export/data-lock pack; Identity Vault.


## Update 2026-09-15: screen audit, Reports, performance

- **Every screen, every role.** `e2e/all-screens-audit.spec.ts` signs in as each of the
  eight roles and opens every screen plus case, KII and document detail pages at 1366px
  and 375px, failing on server errors, refused data calls, crashes, endless loading or
  sideways scrolling. It found and fixed: the PROIT panel and the reserve-pairing list
  refusing roles without those grants (KII RA, Contact RA), and two wide menus pushing
  pages sideways on phones.
- **Reports** (`16` "Reports screen"): fieldwork analytics with charts and table views.
- **Performance.** Measured every data endpoint and removed the per-row queries: the
  Main-400 register (40 → 2 queries per page), KII register, analysis and operational
  exports (one consent query per submission), and the Follow-ups screen (several queries
  per invited case → a fixed handful). Invitation-link checks no longer load every
  invitation's full row. New indexes on the audit log, consent history and submissions.
  `tests/test_query_counts.py` fails if any of these starts growing with the data again.
  The frontend no longer refetches every query when a tab regains focus, and no longer
  retries refusals. Suites: backend 356 passed; E2E 43 passed, 2 skipped (WhatsApp, and
  Form PDFs where no KoboToolbox is connected).

## Update 2026-09-15 (evening): test case reset, imported contacts cleaned

- **SID-2026-000400 reset.** The PI's end-to-end test case was advanced S03 → S10 QA passed through
  the state machine on his instruction, then reset to a fresh S03 case like the other 399:
  - Removed: its test submission in KoboToolbox and, in the portal, 3 test respondents,
    1 invitation, 3 consent records, the QA-passed submission and its QA decision, and an
    empty PROIT draft.
  - Kept: the earlier audit entries; the reset itself is audited as
    `sampling.test_case_reset`.
  - Backup: `/srv/agribiz-drp/backups/test-case-reset-SID-2026-000400-20260915-201353/`.
- **Imported contact details split into proper fields** (`clean_imported_contacts`, audited
  as `contacts.imported_contacts_cleaned`, originals backed up first). Names, phone lists,
  WhatsApp numbers and emails now sit in their own fields, and a multi-number phone field no
  longer produces a broken WhatsApp link. This does not add numbers: most Main cases still
  have no contact details and must be collected (item 3 above).
