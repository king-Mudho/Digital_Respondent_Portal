"""The KoboToolbox form that holds a case's pre-interview profile: what was known before the interview (from
public sources, with the source), what the respondent said about each fact, and the reconciled position.

One definition drives both the XLSForm the researcher deploys (deploy/kobo/build_proit_form.py) and the submission
the portal sends (kobo_submit.py), so the two cannot drift. Pure data -- no Django imports."""

FORM_TITLE = "ABF-FST PROIT Interview Profile"
FORM_VERSION_LABEL = "v1.0"

# (name, type, label, required). Element names are the XLSForm names; they sit inside the group `profile`.
PROFILE_FIELDS = [
    ("record_id", "text", "Record ID (Sample ID for a questionnaire case, KII ID for a key informant)", True),
    ("record_type", "text", "Record type (QUAN or KII)", True),
    ("organisation", "text", "Organisation", False),
    ("reconciliation_status", "text", "Reconciliation status (RECONCILED or UNRESOLVED)", True),
    ("protocol_deviation", "text", "Protocol deviation recorded (yes/no)", False),
    ("deviation_note", "text", "Why reconciliation could not be finished", False),
    ("locked_at", "text", "Profile locked before the interview (date and time)", False),
    ("interview_completed_at", "text", "Interview completed (date and time)", False),
    ("ai_assisted", "text", "Any fact came from AI desk research and was accepted by a researcher (yes/no)", False),
    ("facts_total", "text", "Facts on the profile", False),
    ("facts_verified", "text", "Facts verified with the respondent", False),
    ("facts_reconciled", "text", "Facts with a reconciled value", False),
    ("background_questions_avoided", "text", "Background questions the interview did not need to ask", False),
    ("burden_reduction_score", "text", "Respondent burden reduction score", False),
    ("known_evidence_summary", "text", "What was already known (evidence summary)", False),
    ("unresolved_gaps", "text", "What was not available publicly", False),
    ("contradictions", "text", "Contradictions between sources", False),
    ("priority_probe_questions", "text", "Priority probe questions", False),
]

# One repeat instance per fact on the profile.
REPEAT_NAME = "fact_repeat"
REPEAT_FIELDS = [
    ("fact_id", "text", "Fact ID", True),
    ("fact_label", "text", "Fact", False),
    ("fact_module", "text", "Module", False),
    ("documentary_value", "text", "Known before the interview (public sources)", False),
    ("confidence", "text", "Confidence", False),
    ("gap_classification", "text", "Gap classification", False),
    ("sources", "text", "Sources (title | publisher | date | tier | link)", False),
    ("verification_status", "text", "What the respondent said (verification status)", False),
    ("respondent_value", "text", "Respondent's own value", False),
    ("verification_comment", "text", "Interviewer comment", False),
    ("reconciled_value", "text", "Reconciled value (the coded position)", False),
]
GROUP_NAME = "profile"
META_FIELDS = {"start": "start", "end": "end", "today": "today", "username": "username"}
