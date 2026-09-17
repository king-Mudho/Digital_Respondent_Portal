# 14 — Documentary evidence module

Supports triangulation as a provenance-controlled evidence repository, not a general
file dump.

## Fields

Per `DocumentRecord` (`05_DATABASE_ARCHITECTURE.md`): Document_ID; organisation/
institution; title; author/speaker; publication/event date; source URL or repository
reference; document type (official/secondary/platform classification); authenticity/
provenance assessment and verification date; geographic scope and value chain; NFM,
BANK, DGR, AGC, INS and FST construct tags; ABI-dimension **relevance tags only** — never
a score or weighted figure, since the ABI scoring engine is out of scope for this
portal entirely (`20_EMBEDDING_WITH_ABI.md`, `25_FUTURE_ABI_ENGINE_PHASE4.md`); evidence
extract/quotation reference and interpretive memo; triangulation link to QUAN/KII
findings; reviewer, QA status and inclusion decision.

## Provenance and QA

Every document goes through `authenticity_assessment` (`UNVERIFIED → VERIFIED` or
`DISPUTED`) before it can move to `qa_status = INCLUDED`. A reviewer is always recorded.
Documents flagged `DISPUTED` are retained (never silently deleted) with the dispute
reason in `interpretive_memo`, for the PI to adjudicate.

## Target

50–75 documentary records (`00_PROJECT_MASTER.md`), tracked by source type and ABF-FST
construct on the KII/document dashboard, with evidence gaps requiring targeted
collection surfaced by the Documentary Evidence Agent (`17_AI_FIELD_COORDINATOR.md`) for
researcher verification — the agent assists metadata extraction and construct-mapping
suggestions only; inclusion and construct-tag decisions remain human.

## AI-assisted coding of the KoboToolbox Document Analysis Tool (PI decision, 17 Sep 2026)

The Document Analysis Tool's Sections B–L (evidence-strength ratings, hypothesis-support
codes, authenticity calls) are this study's documentary-analysis method, in the same
sense the paragraph above already draws for construct-mapping: extraction assistance is
fine, but the analytical judgment stays human. The portal's **Auto-fill** feature
(`apps/evidence/ai_coding.py`) applies that same line to the Kobo form itself — it drafts
a full answer set from the uploaded source file, but a Documentary RA reviews and edits
every field in the portal before anything is submitted to KoboToolbox
(`apps/evidence/kobo_submit.py`). Every AI-assisted draft and its eventual submission are
audited, so this file's methodology claim ("inclusion decisions remain human") stays true
for the coding as a whole, not only for construct tags.
