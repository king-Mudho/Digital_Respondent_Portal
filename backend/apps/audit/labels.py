"""Turns an AuditEvent's machine action code ("sampling.status_reset_after_test_cleanup") and its metadata
dict into what a person reads on the Audit Log screen: a short label ("Sample case status reset") and a
one-line detail ("S07 -> S03 (test cleanup)"). The raw action code stays in the API response too, for
anyone who wants the exact string, but the screen leads with this.

ACTION_LABELS covers every action code log_action() is called with anywhere in the codebase, plus the
handful of one-off actions recorded directly against the database during the 2026-09-22 test-data cleanup
(sampling.status_reset_after_test_cleanup and its siblings) -- see docs/ manuals changelog. An action added
later without an entry here still shows something readable (its code, unslugified), not blank.
"""

ACTION_LABELS: dict[str, str] = {
    "accounts.email_changed": "Account email changed",
    "accounts.staff_accounts_created": "Staff accounts created",
    "consent.recorded": "Consent recorded",
    "consent.withdrawn": "Consent withdrawn",
    "consent.withdrawal_processed": "Participation withdrawn",
    "contacts.imported_contacts_cleaned": "Imported contacts cleaned up",
    "contacts.respondent_updated": "Respondent contact details updated",
    "document.ai_draft_edited": "AI draft edited",
    "document.ai_draft_generated": "AI draft generated",
    "document.authenticity_assessed": "Document authenticity assessed",
    "document.copied_for_chapter": "Document copied for another chapter",
    "document.created_from_file": "Document record created from an uploaded file",
    "document.details_filled_by_ai": "Document details filled in by AI",
    "document.file_downloaded": "Document source file downloaded",
    "document.file_removed": "Document source file removed",
    "document.file_uploaded": "Document source file uploaded",
    "document.kobo_submission_created": "Document coding submitted to KoboToolbox",
    "document.kobo_submission_removed_in_kobo": "Document submission found removed from KoboToolbox",
    "document.qa_decision_reset_after_test_cleanup": "Document coding decision reset (test cleanup)",
    "document.qa_status_set": "Document QA decision recorded",
    "eligibility.checked": "Respondent eligibility checked",
    "export.analysis_generated": "De-identified analysis export generated",
    "export.operational_generated": "Operational export generated",
    "invitation.emailed": "Invitation emailed",
    "invitation.issued": "Invitation issued",
    "invitation.revoked": "Invitation revoked",
    "invitations.issue_denied_not_invitable": "Invitation attempt refused (case not invitable)",
    "kii.coding_completed_from_kobo": "KII coding marked complete from KoboToolbox",
    "kii.participant_name_corrected": "KII participant name corrected",
    "kii.status_changed": "KII status changed",
    "kii.status_reset_after_test_cleanup": "KII status reset (test cleanup)",
    "kobo.data_exported": "Submissions exported from KoboToolbox",
    "kobo.reconciliation_sample_id_mismatch": "Reconciliation found a Sample ID mismatch",
    "kobo.reconciliation_unverified_submission": "Reconciliation found an unverified submission",
    "kobo.submission_copy_emailed": "Submission copy emailed",
    "kobo.submission_pdf_downloaded": "Submission PDF downloaded",
    "messaging.follow_up_sent": "Follow-up message sent",
    "messaging.wording_approved": "Message wording approved",
    "proit.ai_proposal_accepted": "AI research finding accepted",
    "proit.ai_proposal_rejected": "AI research finding rejected",
    "proit.ai_research_completed": "AI desk research completed",
    "proit.ai_research_failed": "AI desk research failed",
    "proit.ai_research_started": "AI desk research started",
    "proit.field_reconciled": "PROIT fact reconciled",
    "proit.field_verified": "PROIT fact verified with respondent",
    "proit.interview_completed": "PROIT interview marked complete",
    "proit.kobo_submission_created": "PROIT profile sent to KoboToolbox",
    "proit.protocol_deviation_recorded": "Protocol deviation recorded",
    "qa.decision": "QA decision recorded",
    "qa.exception_assigned": "QA exception assigned",
    "qa.exception_resolved": "QA exception resolved",
    "qa.threshold_changed": "QA threshold changed",
    "qa.thresholds_approved": "QA thresholds approved",
    "reserve.activated": "Reserve case activated",
    "sample_case.deleted": "Sample case deleted",
    "sample_case.match_cleared": "Reserve match cleared",
    "sample_case.matched": "Reserve case matched",
    "sampling.bulk_assignment": "Cases bulk-assigned to a Contact RA",
    "sampling.bulk_workflow_transition": "Cases moved forward in bulk",
    "sampling.invalid_workflow_transition": "Invalid workflow transition attempted",
    "sampling.status_reset_after_test_cleanup": "Case status reset (test cleanup)",
}

# Keys checked in this order for the one-line "detail" summary; the first match found wins, then any
# remaining recognised keys are appended. Unrecognised keys are dropped from the summary (still visible in
# the raw metadata, which the API still returns in full) rather than cluttering it with internal ids.
_DETAIL_KEYS: list[tuple[str, str]] = [
    ("from", ""), ("to", ""),  # rendered together as "from -> to" below
    ("sample_id", ""), ("kii_id", ""),
    ("filename", "file"), ("reason", "reason"), ("note", "note"),
    ("channel", "channel"), ("decision", "decision"), ("status", "status"),
    ("field_id", "field"), ("count", "count"), ("moved", "moved"), ("sample_ids", "cases"), ("proposed", "proposed"),
    ("not_found", "not found"), ("searches", "searches"), ("submissions", "submissions"),
    ("old", "was"), ("new", "now"),
]


def describe(action: str, metadata: dict | None) -> tuple[str, str]:
    """(label, detail). label is always non-empty; detail is "" when metadata has nothing worth summarising."""
    label = ACTION_LABELS.get(action) or action.replace(".", " ").replace("_", " ").capitalize()
    metadata = metadata or {}
    parts = []
    if metadata.get("from") is not None and metadata.get("to") is not None:
        parts.append(f"{metadata['from']} → {metadata['to']}")
    for key, shown_as in _DETAIL_KEYS:
        if key in ("from", "to") or key not in metadata or metadata[key] in (None, ""):
            continue
        value = metadata[key]
        if isinstance(value, list):
            value = f"{len(value)} item(s)" if len(value) > 6 else ", ".join(str(v) for v in value)
        text = str(value)
        if len(text) > 80:
            text = text[:77] + "..."
        parts.append(f"{shown_as}: {text}" if shown_as else text)
    return label, " · ".join(parts)
