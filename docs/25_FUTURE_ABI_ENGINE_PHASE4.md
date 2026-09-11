# 25 — Future ABI engine (Phase 4, deferred)

The ABI engine is architecturally anticipated but functionally absent from this
application during primary data collection (Phases 0–3). After measurement-model
validation and finalisation of scoring/weighting rules, the separate, sibling
`agribusiness-bankability/` application — not this repository — becomes the applied
bankability tool, fed by a one-way, PI-approved data export from this portal's
de-identified analytical dataset. See `20_EMBEDDING_WITH_ABI.md` for why this is a data
pipeline, not a shared codebase or a shared deployment.

## What Phase 4 will need (for future reference, not built here)

- A validated ABI input questionnaire, informed by this study's QUAN/KII/document
  findings.
- A versioned scoring algorithm and dimension weights (the ABI project's own
  `FrameworkVersion` mechanism already exists for this — see the ABI project's
  `05_DATABASE_ARCHITECTURE.md` and `10_SCORING_ENGINE.md`).
- Overall ABI score normalised to 0–100 where methodologically approved.
- Dimension-level profile and confidence/quality indicators, potentially informed by
  this portal's `EvidenceRecord`-equivalent evidence-level data.
- Benchmarking against an appropriate reference population, only after sufficient
  validated data exists.
- Action-oriented bankability improvement recommendations clearly separated from any
  lender credit decision.
- An algorithm/version audit trail so a score can be reproduced.

## What this portal must never do in the meantime

Per `AGENTS.md` ground rule 3: never compute, store, or display an ABI score or
financing-readiness figure anywhere in this application, even for a demo, even
internally. `DocumentRecord.construct_tags` may reference ABI dimensions as relevance
tags for triangulation purposes only (`14_DOCUMENTARY_EVIDENCE_MODULE.md`) — a tag is
not a score.
