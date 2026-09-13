# 32 — ResearchOS engineering brief: gap analysis against the built system

Source: `ABF-FST_ResearchOS_Software_Engineering_Innovation_Improvement_Propositions_v1.0`
(13 September 2026). This document maps that brief's 19-item backlog, 10 non-negotiable
principles, 10-point sprint and Definition of Done onto what is actually deployed, so the
remaining work is a list rather than a re-read.

Status vocabulary is deliberately narrow: **Built** (exists and is tested), **Partial**
(exists but does not meet the brief's acceptance criterion), **Absent** (no code).
Nothing is marked Built on the strength of a docstring — this project has been bitten by
that twice.

---

## 1. Non-negotiable principles (§3)

| | Principle | Status | Note |
|---|---|---|---|
| P1 | Portal-first orchestration | **Built** | Portal owns status, sampling, consent, routing, QA, audit; Kobo is capture only |
| P2 | Stable ABF-ID as linking key | **Built** | `Master_ID`/`Sample_ID` generated server-side, never user-entered; de-identified export keys on them |
| P3 | Evidence-stream separation | **Partial** | Streams are separate *tables* joined by controlled IDs, but contact PII sits in the same database and schema as analytical data — no separate identity store (see A3) |
| P4 | Instrument integrity | **Built** | No questionnaire logic in portal code; Kobo owns it |
| P5 | Human-in-the-loop AI | **n/a** | No AI in the system yet (see A16) |
| P6 | Provenance by default | **Partial** | Strong for PROIT evidence (`EvidenceSource`: source, type, publisher, dates, locator, authority, confidence, creator). Weaker for the documentary corpus (see A10) |
| P7 | Mobile/low-bandwidth first | **Built** | Responsive, verified at 375px; no native app |
| P8 | Security by design | **Partial** | Secrets server-side, httpOnly JWT, RBAC, throttling, backups now scheduled and tested. Missing: MFA-ready admin, encryption at rest, identity separation |
| P9 | Cost observability | **Partial** | Cost per QA-passed QUAN and per completed KII exist; per-mode, per-RA, per-stratum and forecast do not (see §7) |
| P10 | Reproducibility | **Partial** | Consent text, instruments and code are versioned. Exports, transformations and data-lock events are not (see A17) |

## 2. Priority backlog (§5)

### P0 — "before/at controlled launch"

| | Module | Status | What is missing |
|---|---|---|---|
| A1 | Sampling Control Engine | **Built** | Main lock, paired reserves, five authorised replacement reasons, audit trail, validated pairing |
| A2 | Consent & Ethics Service | **Partial** | Versioned PIS, separate recording consent, consent-gated routing all built. **Withdrawal/status log is absent** — the model records GIVEN/DECLINED/WITHDRAWN but there is no withdrawal workflow or screen |
| A3 | Identity Vault & RBAC | **Partial** | RBAC fully built (8 roles, nav-scoped, tested). **Identity Vault absent** — PII is not in a separated store. MFA-ready admin absent. Session timeout is JWT expiry only |
| A4 | Kobo Sync & Reconciliation | **Partial** | Webhook + scheduled reconciliation + content-hash edit detection + mismatch flagging built. **Duplicate quarantine and idempotency keys absent** — a mismatched submission is flagged, not quarantined into a holding state |
| A5 | Audit/Event Ledger | **Partial** | `AuditEvent` covers the listed actions and is correctly attributed. **Acceptance criterion "case timeline reconstructable end-to-end" is not met** — there is no timeline view; you would reconstruct it by querying |
| A6 | QA Exception Engine | **Partial** | Rules evaluate and create `QAEvent`s; queue and human decision built. **"Daily exception queue with owner/status" absent** — `QAEvent` has no owner, status or resolution field, so exceptions cannot be assigned or tracked to closure |
| A7 | Cost Management Engine | **Partial** | `CostEvent` with categories, cost per usable QUAN/KII, category breakdown. **Absent:** per-mode/RA/stratum attribution, burn rate, forecast at completion, cost-to-close-stratum |

### P1 — "during fieldwork"

| | Module | Status | What is missing |
|---|---|---|---|
| A8 | PROIT Workflow | **Built** | Source-backed pre-profile, human review and lock, respondent confirm/correct/decline, three values kept separate, protected constructs never pre-filled |
| A9 | Research Command Centre | **Partial** | Six dashboards exist. **The one-screen control surface with the six KPI panels of §6 does not** — and several §6 metrics are unimplemented (see docs/16 "As built") |
| A10 | Evidence Provenance Passport | **Partial** | PROIT evidence carries most required fields. **`DocumentRecord` does not** — no retrieval date, extractor, reviewer-vs-extractor distinction, coding version, or confidence/status against the §9 field list |
| A11 | Mixed-Methods Evidence Matrix | **Absent** | No H1–H5c or ABI-dimension mapping anywhere; no `EvidenceCode` entity |
| A12 | Mode-Effect Monitor | **Partial** | Administration mode is captured and shown on the QA dashboard. **No comparison of completion/missingness/duration/composition by mode** |
| A13 | Respondent Burden Metrics | **Absent** | PROIT records verifications but nothing measures time saved, questions avoided, abandonment or correction rate |
| A14 | Secure Document Repository | **Partial** | Document records with QA state exist. **No file upload, no checksum/hash, no version history** — documents are referenced by URL/citation, not stored |

### P2/P3 — later phases

| | Module | Status |
|---|---|---|
| A15 | Evidence Graph | **Absent** (P2, after core stability) |
| A16 | AI Assistance & Governance | **Absent** (P2) |
| A17 | Reproducible Export Pack | **Partial** — two CSV exports exist; no codebook, data dictionary, QA log, instrument version or provenance manifest, and no `DataLock` entity |
| A18 | Post-Validation ABI Module | **Absent by design** (P3) — and must stay absent; see `AGENTS.md` ground rule 3 |
| A19 | Study Builder / Replication | **Absent** (P3) |

## 3. Core entities (§12)

Present: `SampleCase`, `ConsentRecord` (=ConsentEvent), `ContactEvent`, `QUANSubmission`
(=Submission), `KIIRecord`, `EvidenceSource`, `DocumentRecord`, `PreProfileField`
(=PROITField), `QAEvent`, `CostEvent`, `AuditEvent`.

Absent: **`StudyVersion`** (protocol/instrument/consent versions and approval state — the
versions exist as scattered strings, not an entity), **`IdentityContact`** (the vault),
**`EvidenceCode`** (evidence unit → construct/hypothesis with locator and direction),
**`QAFlag`** as distinct from the append-only `QAEvent`, **`DataLock`**.

## 4. The 10-point immediate sprint (§18)

| | Item | Status |
|---|---|---|
| 1 | Document stack, schema, hosting, auth, backups, integrations | **Built** — README, docs/03, 05, 23, 24 |
| 2 | **Staging and production environments; stop untracked production changes** | **Absent** — production only. docs/23 specifies staging; it was never provisioned. Every change this month has gone straight to production |
| 3 | RBAC, Identity Vault, server-side secrets | **Partial** — RBAC and secrets done; vault absent |
| 4 | SampleCase state machine with Main/Reserve rules | **Built** |
| 5 | Consent/version service and case timeline ledger | **Partial** — ledger yes, timeline view no |
| 6 | Harden Kobo ingestion: ABF-ID validation, duplicate quarantine, reconciliation | **Partial** — quarantine absent |
| 7 | QA exception queue and mode capture | **Partial** — no owner/status |
| 8 | CostEvent model and first cost dashboard | **Built** |
| 9 | PROIT provenance/review/verification | **Built** |
| 10 | Automated tests, backup/restore test, deployment notes, **versioned v1.0 release** | **Partial** — 260 backend tests, 25 E2E, backup restore-tested today, deploy notes exist. **No version tag or release has ever been cut** |

## 5. Definition of Done for ResearchOS v1.0 (§15)

| Criterion | Met? |
|---|---|
| Main case traceable import → invitation → consent → submission → QA → data lock | **No** — no data-lock stage, no timeline view |
| Reserve activation impossible without approved reason and paired-case audit trail | **Yes** |
| No analytical export requires names/phone numbers as keys | **Yes** |
| Every accepted Kobo submission has valid ABF-ID, instrument version, mode | **Partial** — ABF-ID and mode validated; instrument version is not captured per submission |
| Every documentary code has source and locator, or is explicitly unresolved | **No** — no `EvidenceCode` |
| Daily QA exceptions visible, assigned, resolvable without editing raw data | **No** — no assignment or status |
| Actual and forecast cost visible and attributable by mode/category | **Partial** — actual by category; no mode attribution, no forecast |
| PROIT cannot pre-answer protected constructs; preserves corrections | **Yes** |
| AI suggestions distinguishable from human-reviewed records | **n/a** — no AI |
| Versioned reproducible data-lock package generatable | **No** |
| Backup restoration and core security controls tested | **Partial** — backup restore verified 13 Sep; no independent security review |
| Usable on a low-cost smartphone and constrained connection | **Yes** |

---

## 6. What this means

The brief's **P0 tranche is roughly 60% complete**. The system is strong exactly where
this project has spent its attention — sampling integrity, consent gating, RBAC, audit
attribution, PROIT — and thin in five specific places that share a character: they are
about *operating* the study day to day and *proving* afterwards what happened.

The five P0-level gaps, in the order they block things:

1. **Staging environment** (§18.2). Everything else on this list is a production change,
   and there is currently nowhere to rehearse one. This should come first on sequencing
   grounds, not merit.
2. **QA exception ownership** (A6) — an exception queue nobody can be assigned is a list,
   not a workflow. Directly blocks the "daily exceptions assigned and resolvable" DoD item.
3. **Kobo duplicate quarantine** (A4) — currently a mismatched submission is flagged and
   left in the dataset. The brief wants it held out.
4. **Case timeline** (A5) — the acceptance criterion is explicitly end-to-end
   reconstruction, which is also what an examiner would ask to see for a single case.
5. **Cost attribution and forecast** (A7) — the brief makes cost-effectiveness a research
   *finding* (§7, §16), not an admin convenience. Cost per mode is the comparison the
   thesis wants to make, and it cannot currently be produced.

Two further items are architecturally significant and should be decided rather than
assumed:

- **Identity Vault** (A3). Separating PII into its own store is the single largest change
  in the brief. It touches every model with a contact field, the exports, and the
  permission classes. It is genuinely valuable for an examined study — but it is a
  refactor of live schema holding real data, and it needs a migration plan and a rehearsal
  environment before it is attempted. This is the strongest argument for doing staging
  first.
- **`StudyVersion` / `DataLock` / reproducible export pack** (A17, §15). These are what
  make the thesis reproducible and are what an external examiner is most likely to ask to
  exercise. They are additive rather than invasive, so they carry far less risk than the
  vault.

Nothing in the brief conflicts with the frozen instruments or the ethics controls. §19's
change-control rule is already this project's practice and is now also `AGENTS.md`
ground rule 6; §20 explicitly subordinates this backlog to the approved instruments and
ethics decisions, which matches the existing hierarchy.
