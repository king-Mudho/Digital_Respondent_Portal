# 17 — AI Field Coordinator layer

AI operates as a decision-support and workflow layer, never as an autonomous research
respondent, sampler, or adjudicator (`AGENTS.md` ground rule 3 extends this: it also
never touches ABI scoring, since that engine doesn't exist inside this application at
all).

## The six agents

**Sampling Control Agent** — flags duplicates, reserve-lock violations, stratum
shortfalls, and cases approaching nonresponse exhaustion (against the sequence in
`12_CONTACT_CRM_AND_MESSAGING.md`).

**Contact Queue Agent** — prioritises due follow-ups and identifies cases with missing
respondent/gatekeeper information.

**QUAN QA Agent** — evaluates submissions against the thresholds in
`15_QA_AND_DATA_QUALITY.md`, producing hard-stop queries and soft flags for the QA
queue; never auto-accepts or auto-rejects a record.

**KII Coordinator Agent** — tracks quota coverage, appointments, transcript backlog and
thematic evidence gaps.

**Documentary Evidence Agent** — assists provenance tracking, metadata extraction and
construct-mapping suggestions for researcher verification; never sets `qa_status`
itself.

**Cost Control Agent** — tracks burn rate, cost per usable response, and whether
proposed travel meets the cost/coverage trigger defined by the PI/Field Coordinator.

## Implementation note

Each agent is a scheduled or on-demand backend job (Celery task or a plain API-triggered
service function, per `04_TECH_STACK.md`) that reads current state and writes flags/
recommendations — never a chat-style autonomous loop with its own write access beyond
flagging. This keeps every agent's output reviewable and reversible.

## Human approval remains mandatory for

Respondent eligibility, reserve activation, exclusion/rejection of a research record,
qualitative interpretation, ethics deviations, and final data lock — unchanged from the
v1.0 blueprint and restated in `AGENTS.md` ground rule 6 and throughout this
documentation set as each relevant module is specified.
