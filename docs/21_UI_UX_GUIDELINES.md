# 21 — UI/UX guidelines

## Legitimacy-first design principle

The landing and invitation-validation screens must establish study legitimacy
immediately: study title, Chinhoyi University of Technology affiliation, principal
researcher, brief purpose, privacy statement, contact/support option, and a single clear
action to continue with the invitation. Avoid displaying complex research constructs or
any hint of a provisional score.

Branding should emphasise university research legitimacy and confidentiality.
Deliberately avoid commercial/fintech branding patterns (loan-application-style
progress bars, "approval" language, currency-forward visuals) that could make a
respondent believe participation is itself a financing application, or that a lender
will see their responses — see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.

## Design tokens

Implemented as Tailwind config + CSS variables (not invented ad hoc per component,
matching ABI's own discipline):

- **Colour**: a calm, institutional palette distinct from ABI's own (ABI uses green/gold
  per its sponsor branding) so the two are visually distinguishable if a user somehow has
  both open — propose a blue/neutral academic palette, confirm with the PI/sponsor before
  Phase 1 UI work.
- **Typography**: legible at small sizes on low-cost Android screens; generous line
  height for consent/information text.
- **Status chips**: workflow status (S00–S16) and QA decisions always carry a text
  label, never colour alone (`19_LANGUAGE_AND_ACCESSIBILITY.md`).

## Mobile-first constraints

- Design and test at 360–400px width first, not as an afterthought.
- Large tap targets for the consent/eligibility flow — this is often completed on a
  phone, sometimes RA-assisted, sometimes by an older executive with a large-format
  phone.
- Minimise data-heavy assets; the respondent flow must load acceptably on variable/poor
  connectivity, matching NFR-1/NFR-2 (`02_PRODUCT_REQUIREMENTS.md`).

## Research Operations Centre patterns

- Table-dense list/detail views (A03 Main-400 register, A06 QA queue) prioritise
  scanability and filtering over visual polish — this is a working tool for RAs and the
  Field Coordinator, not a marketing surface.
- Every list view supports the filters relevant to its dashboard
  (`16_DASHBOARDS_AND_REPORTING.md`): province, stratum, workflow status, QA status, date
  range.
