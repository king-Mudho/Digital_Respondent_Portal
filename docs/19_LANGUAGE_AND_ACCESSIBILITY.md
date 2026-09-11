# 19 — Language & accessibility

The v1.0 blueprint implicitly assumed English-only respondent-facing content without
stating the decision. This document closes that gap by making the decision explicit —
an ethics reviewer is likely to ask this question directly, and an implicit assumption
is not a defensible answer.

## Language decision (v1.0)

**English-only for v1.0, with the decision explicitly documented and flagged for
revisit.** Given the national sampling frame, some respondents or gatekeepers may be
materially better served in Shona or Ndebele, particularly for informed-consent
comprehension — this is recognised, not dismissed, but full localisation is deferred
past the immediate Phase 1 MVP window given the timeline pressure against the 30
November 2026 data lock (`26_MVP_PHASING_AND_ROADMAP.md`).

**Mitigations required even within the English-only decision**:

- Participant information and consent text must be written in plain, unambiguous
  English (avoid academic/technical register), reviewed for comprehension by the PI/
  ethics office before use.
- Phone-assisted and WhatsApp-call-assisted administration modes (`11_KOBOTOOLBOX_
  INTEGRATION.md`, codes 03–05) allow an RA to verbally clarify consent and questionnaire
  content in Shona or Ndebele as needed — this is the primary accessibility mitigation
  for v1.0, not a translated interface.
- The eligibility/consent flow's plain-English text is tracked as an explicit open
  question for the PI: confirm whether Shona/Ndebele translated Participant Information
  Sheets should exist even without a fully localised interface, given they are
  comparatively low-cost to produce relative to full UI localisation.

**Revisit trigger for v2**: if the contact dashboard shows a material pattern of
consent-comprehension difficulty or refusal correlated with a specific language
preference, localisation is escalated ahead of `25_FUTURE_ABI_ENGINE_PHASE4.md`'s other
priorities.

## Accessibility baseline (NFR-7, `02_PRODUCT_REQUIREMENTS.md`)

- All form controls labelled (not placeholder-only labels).
- Colour contrast meeting WCAG AA at minimum for respondent-facing screens.
- Fully keyboard-navigable flows for internal Research Operations Centre screens.
- Text sized and laid out for small, low-cost Android screens first — see
  `21_UI_UX_GUIDELINES.md`.
- No content or interaction that depends solely on colour to convey QA/status meaning
  (e.g. status chips carry text labels, not colour alone).
