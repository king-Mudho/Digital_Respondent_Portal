# 15 — QA & data quality

The v1.0 blueprint named QA triggers ("unusual duration", "logic failures", "coverage
issues") throughout Sections 8, 12.4 and 13 without numeric definitions, which blocked
the QUAN QA Agent from being built. This document gives concrete default thresholds.

**These are proposed engineering defaults, not yet PI-confirmed research decisions.**
Per `AGENTS.md`'s Open Questions convention, they are logged as an open question in
`27_AGENT_EXECUTION_PLAN.md` for explicit PI sign-off before Phase 1 QA-engine work
starts — set concrete numbers precisely so the PI has something specific to approve or
adjust, rather than an abstract "define this later."

## QA rule thresholds (seeded as `QARuleThreshold` rows — config, not code)

| Code | Proposed default | Trigger |
|---|---|---|
| `min_plausible_duration_seconds` | 300 (5 minutes) | Flag `QUANSubmission` if `completion_seconds` is below this — implausibly fast for the instrument. |
| `max_plausible_duration_seconds` | 5400 (90 minutes) | Flag if above this — likely left open/abandoned and resumed, or interrupted. |
| `max_missing_optional_fields_percent` | 10% | Soft-flag (QUERY) if more than this share of optional fields are blank. |
| `hard_stop_missing_required_fields` | any | Any required field missing is always a hard stop (REJECT pending correction), never a soft flag. |
| `duplicate_master_id_window_hours` | 24 | Flag two submissions sharing a Master_ID within this window as a possible duplicate for manual review. |
| `logic_violation_hard_stop_rules` | list, seeded from the Kobo form's own skip-logic definition | A skip-logic violation Kobo itself could not have produced (i.e., a raw-payload inconsistency) is always a hard stop — this is corruption/tampering-class, not a soft flag. |
| `logic_violation_soft_flag_rules` | list, PI-defined per question | Substantively implausible but not structurally impossible answer combinations (e.g., very high turnover band with very low worker count) are soft flags for QA reviewer judgement, not automated rejection. |
| `mode_imbalance_alert_ratio` | any single `administration_mode` exceeding 70% of submissions in a rolling 7-day window | Flags the sampling/contact dashboard, not individual submissions — signals a possible mode-effect risk worth PI attention. |

## Hard-stop vs. soft-flag principle

A **hard stop** blocks a submission from reaching `QA_PASSED` until corrected or
explicitly overridden by a human reviewer with a note (never auto-corrected). A **soft
flag** places the submission in the QA queue for reviewer judgement but does not block
progress by itself — it is a prioritisation signal, not a rejection. This distinction is
what makes the QUAN QA Agent (`17_AI_FIELD_COORDINATOR.md`) safe to run automatically:
it can flag and queue without ever silently rejecting a real respondent's data.

## QA decision flow

1. On reconciliation (`11_KOBOTOOLBOX_INTEGRATION.md`), every new/updated
   `QUANSubmission` is evaluated against every active `QARuleThreshold`.
2. Any hard-stop condition sets `qa_status = QUERY` and creates a `QAEvent` with
   `decision = QUERY` and the triggering rule code.
3. A human QUAN/Kobo QA RA reviews the queue (`06_API_ARCHITECTURE.md` `qa/queue/`),
   resolving each item to `ACCEPT`, a corrected re-query to the field team, or `REJECT`
   (with a mandatory note either way).
4. Only a human-recorded `QAEvent.decision = ACCEPT` moves `qa_status` to `QA_PASSED`
   and admits the record into the versioned analytical dataset — this is never automatic
   even when zero rules triggered, preserving a human checkpoint on every record before
   data lock.

## QA turnaround monitoring

The QUAN QA dashboard (`16_DASHBOARDS_AND_REPORTING.md`) tracks median and 90th-
percentile QA queue turnaround time; a target of ≤ 48 hours median turnaround is
proposed as a default operational target, also PI-adjustable.
