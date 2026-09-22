"""Read-only test/pilot-data smell check, shared by the management command (apps/audit/management/
commands/check_test_data_smells.py, for an on-demand run) and the daily Celery task (apps/audit/tasks.py,
which emails the result). See the command's module docstring for what each check looks for and why --
these are exactly the patterns found and cleaned up by hand on 2026-09-22.

Never deletes or changes anything. Returns (section_title, [line, ...]) pairs; an empty list means clean."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.contacts.models import Respondent
from apps.evidence.models import DocumentRecord
from apps.invitations.models import InvitationToken
from apps.kii.models import KIIRecord
from apps.proit.models import PreProfile

FAST_TURNAROUND = timedelta(hours=2)  # real fieldwork (invite -> consent -> submit -> QA) never happens this fast


def _empty_preprofiles(cutoff):
    qs = PreProfile.objects.filter(prepopulation_locked_at__isnull=True, fields__isnull=True)
    if cutoff:
        qs = qs.filter(created_at__date__gte=cutoff)
    lines = []
    for p in qs.select_related("sample_case", "kii_record"):
        who = p.sample_case.sample_id if p.sample_case_id else p.kii_record.kii_id
        lines.append(f"PreProfile #{p.id} on {who}, created {p.created_at:%Y-%m-%d %H:%M}")
    return "Empty, unlocked pre-interview profiles", lines


def _staff_named_contacts(cutoff):
    staff = {(u.get_full_name() or "").strip().lower(): u.username for u in User.objects.all() if u.get_full_name()}
    staff_emails = {u.email.lower(): u.username for u in User.objects.exclude(email="")}
    lines = []
    for k in KIIRecord.objects.exclude(participant_name=""):
        name = k.participant_name.strip().lower()
        if name in staff:
            lines.append(f"KII {k.kii_id}: participant_name matches staff account '{staff[name]}'")
    respondents = Respondent.objects.exclude(email="")
    if cutoff:
        respondents = respondents.filter(sample_case__updated_at__date__gte=cutoff)
    for r in respondents.select_related("sample_case"):
        email = r.email.strip().lower()
        if email in staff_emails:
            lines.append(f"Respondent #{r.id} (case {r.sample_case.sample_id}): email matches staff account '{staff_emails[email]}'")
    return "Contacts that look like a staff member's own details", lines


def _fast_turnaround_cases(cutoff):
    from apps.kobo.models import QUANSubmission

    lines = []
    qs = QUANSubmission.objects.filter(qa_status="QA_PASSED").select_related("sample_case")
    if cutoff:
        qs = qs.filter(submitted_at__date__gte=cutoff)
    for s in qs:
        invite = InvitationToken.objects.filter(sample_case=s.sample_case).order_by("issued_at").first()
        if invite and s.submitted_at and (s.submitted_at - invite.issued_at) < FAST_TURNAROUND:
            lines.append(f"{s.sample_case.sample_id}: invited {invite.issued_at:%Y-%m-%d %H:%M}, submitted {s.submitted_at:%Y-%m-%d %H:%M} "
                         f"({s.submitted_at - invite.issued_at} later)")
    return "Cases completed implausibly fast for real fieldwork", lines


def _stale_uploaded_documents(cutoff):
    qs = DocumentRecord.objects.exclude(source_file_ref="").filter(kobo_submitted_at__isnull=True)
    if cutoff:
        qs = qs.filter(source_file_uploaded_at__date__gte=cutoff)
    lines = []
    for d in qs:
        if d.source_file_uploaded_at and timezone.now() - d.source_file_uploaded_at > timedelta(days=3):
            lines.append(f"{d.document_id} {d.title!r}: uploaded {d.source_file_uploaded_at:%Y-%m-%d}")
    return "Documents with a file uploaded 3+ days ago, still not submitted", lines


def _unattributed_audit_events(cutoff):
    qs = AuditEvent.objects.filter(user__isnull=True)
    if cutoff:
        qs = qs.filter(created_at__date__gte=cutoff)
    lines = []
    named_ids = {u.id for u in User.objects.all()}
    for e in qs:
        uid = (e.metadata or {}).get("user_id") or (e.metadata or {}).get("issued_by_id") or (e.metadata or {}).get("by_user_id")
        if uid and uid in named_ids:
            lines.append(f"AuditEvent #{e.id} ({e.action}, {e.created_at:%Y-%m-%d}): metadata names user {uid} but user field is blank")
    return "Audit events with a named user but no attribution", lines


def test_data_smells(*, since=None) -> list[tuple[str, list[str]]]:
    """Runs every check and returns only the sections that found something."""
    checks = [_empty_preprofiles, _staff_named_contacts, _fast_turnaround_cases, _stale_uploaded_documents, _unattributed_audit_events]
    results = [check(since) for check in checks]
    return [(title, lines) for title, lines in results if lines]
