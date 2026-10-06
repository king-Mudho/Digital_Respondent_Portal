"""
Respondents and outreach workbook (PI request, 2026-10-06): everyone the study can contact or has contacted, and every
invitation sent, in one download. The operational export lists only organisations that have SUBMITTED a questionnaire,
so until now there was no single record of who had been invited, how, and what happened next.

Three sheets:
  * Main-400 respondents -- one row per person on a contactable case (Main, or an activated Reserve); a case with
    nobody recorded yet still gets a row, so the whole sample is visible. Contact details, the latest invitation and
    its progress, reminders recorded as sent, and the last logged contact attempt.
  * KII informants -- one row per KII record, with its contact details and latest self-service invitation.
  * Invitation log -- every invitation ever issued, Main-400 and KII: channel, when, by whom, whether the portal
    emailed it, and how far it got.

It holds names and contact details, so it is PI-only (IsAdminOnly), like the operational export, and each download is
audited. What the portal cannot know is said plainly: a WhatsApp invitation is recorded when it is created, but
WhatsApp itself does not tell the portal whether it was sent, delivered or read.
"""

from collections import defaultdict
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1D2F4F")


def _when(value) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if value else ""


def _day(value) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d") if value else ""


def _sheet(wb, title, columns, rows, first=False):
    sheet = wb.active if first else wb.create_sheet()
    sheet.title = title
    sheet.append([name for name, _width in columns])
    for cell in sheet[1]:
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
    for row in rows:
        sheet.append(row)
    for index, (_name, width) in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    return sheet


def _audit_by_object(action: str) -> dict:
    """{object_id: (first event's time, its user)} for one audit action -- who issued or emailed each invitation."""
    from apps.audit.models import AuditEvent

    found = {}
    for object_id, created_at, user in (
        AuditEvent.objects.filter(action=action).select_related("user").order_by("created_at")
        .values_list("object_id", "created_at", "user__username")
    ):
        found.setdefault(object_id, (created_at, user or "system"))
    return found


def build_outreach_workbook() -> tuple[bytes, dict]:
    """(xlsx bytes, counts for the audit entry)."""
    from django.db.models import Q

    from apps.contacts.kii_finder import organisation_name
    from apps.contacts.models import ContactEvent
    from apps.invitations.models import InvitationToken
    from apps.kii.models import KIIInvitationToken, KIIRecord
    from apps.messaging.models import MessageLog
    from apps.sampling.models import ReserveStatus, SampleCase, SampleType

    issued = _audit_by_object("invitation.issued")
    emailed = _audit_by_object("invitation.emailed")
    kii_issued = _audit_by_object("kii_invitation.issued")
    kii_emailed = _audit_by_object("kii_invitation.emailed")

    cases = list(
        SampleCase.objects.filter(Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED))
        .select_related("organisation", "assigned_ra").prefetch_related("respondents").order_by("sample_id")
    )
    tokens = defaultdict(list)
    for token in InvitationToken.objects.order_by("issued_at"):
        tokens[token.sample_case_id].append(token)
    reminders = defaultdict(list)
    for log in MessageLog.objects.filter(sample_case__isnull=False).select_related("template").order_by("created_at"):
        reminders[log.sample_case_id].append(log)
    attempts = defaultdict(list)
    for event in ContactEvent.objects.order_by("occurred_at"):
        attempts[event.sample_case_id].append(event)

    main_columns = [
        ("Sample ID", 17), ("Sample type", 10), ("Organisation", 36), ("Province", 16), ("District", 16),
        ("Case status", 10), ("Contact RA", 16), ("Respondent", 28), ("Role", 22), ("Eligible", 9),
        ("Phone", 18), ("WhatsApp", 18), ("Email", 30), ("Gatekeeper", 22), ("Gatekeeper contact", 22),
        ("Invitations issued", 10), ("Latest invitation: channel", 12), ("Latest invitation: issued", 17),
        ("Latest invitation: by", 16), ("Latest invitation: status", 18), ("Latest invitation: expires", 12),
        ("Emailed by the portal", 17), ("Reminders recorded as sent", 12), ("Last reminder", 17),
        ("Contact attempts logged", 10), ("Last attempt", 17), ("Last attempt: channel / outcome", 24),
    ]
    main_rows, people = [], 0
    for case in cases:
        org = case.organisation
        ra = case.assigned_ra
        latest = tokens[case.id][-1] if tokens[case.id] else None
        by = issued.get(str(latest.pk), (None, ""))[1] if latest else ""
        sent_email = emailed.get(str(latest.pk), (None, ""))[0] if latest else None
        logs, events = reminders[case.id], attempts[case.id]
        last_event = events[-1] if events else None
        shared = [
            len(tokens[case.id]), latest.channel if latest else "", _when(latest.issued_at) if latest else "", by,
            latest.status if latest else "", _day(latest.expires_at) if latest else "", _when(sent_email),
            len(logs), _when(logs[-1].sent_at or logs[-1].created_at) if logs else "",
            len(events), _when(last_event.occurred_at) if last_event else "",
            f"{last_event.channel} / {last_event.outcome}" if last_event else "",
        ]
        head = [case.sample_id, case.sample_type, org.name if org else "", org.get_province_display() if org else "",
                org.district if org else "", case.workflow_status or "", (ra.get_full_name() or ra.username) if ra else "Unassigned"]
        respondents = sorted(case.respondents.all(), key=lambda r: (r.is_eligible is not True, r.id))
        if not respondents:
            main_rows.append(head + [""] * 8 + shared)
        for person in respondents:
            people += 1
            eligible = {True: "Yes", False: "No"}.get(person.is_eligible, "Not screened")
            main_rows.append(head + [
                person.full_name, person.get_role_category_display() if person.role_category else "", eligible,
                person.phone, person.whatsapp_number, person.email, person.gatekeeper_name, person.gatekeeper_contact,
            ] + shared)

    kii_tokens = defaultdict(list)
    for token in KIIInvitationToken.objects.order_by("issued_at"):
        kii_tokens[token.kii_record_id].append(token)
    kii_columns = [
        ("KII ID", 10), ("Organisation", 36), ("Stakeholder category", 26), ("Informant", 30), ("Role", 26),
        ("KII status", 11), ("Phone", 18), ("WhatsApp", 18), ("Email", 30), ("Invitations issued", 10),
        ("Latest invitation: channel", 12), ("Latest invitation: issued", 17), ("Latest invitation: by", 16),
        ("Latest invitation: status", 16), ("Latest invitation: expires", 12), ("Emailed by the portal", 17),
    ]
    kii_records = list(KIIRecord.objects.select_related("organisation").order_by("kii_id"))
    kii_rows = []
    for record in kii_records:
        latest = kii_tokens[record.id][-1] if kii_tokens[record.id] else None
        kii_rows.append([
            record.kii_id, organisation_name(record), record.stakeholder_category, record.participant_name,
            record.participant_role, record.status, record.phone, record.whatsapp_number, record.email,
            len(kii_tokens[record.id]), latest.channel if latest else "", _when(latest.issued_at) if latest else "",
            kii_issued.get(str(latest.pk), (None, ""))[1] if latest else "", latest.status if latest else "",
            _day(latest.expires_at) if latest else "", _when(kii_emailed.get(str(latest.pk), (None, None))[0]) if latest else "",
        ])

    case_by_id = {case.id: case for case in cases}
    log_columns = [
        ("Type", 9), ("Sample ID / KII ID", 17), ("Organisation", 36), ("Channel", 11), ("Issued", 17),
        ("Issued by", 16), ("Status", 18), ("Expires", 12), ("Emailed by the portal", 17), ("Revoked", 17),
        ("Revoke reason", 30),
    ]
    log_rows = []
    for token in InvitationToken.objects.select_related("sample_case__organisation").order_by("issued_at"):
        case = case_by_id.get(token.sample_case_id) or token.sample_case
        log_rows.append([
            "Main-400", case.sample_id, case.organisation.name if case.organisation else "", token.channel,
            _when(token.issued_at), issued.get(str(token.pk), (None, ""))[1], token.status, _day(token.expires_at),
            _when(emailed.get(str(token.pk), (None, None))[0]), _when(token.revoked_at), token.revoked_reason,
        ])
    record_by_id = {record.id: record for record in kii_records}
    for token in KIIInvitationToken.objects.order_by("issued_at"):
        record = record_by_id[token.kii_record_id]
        log_rows.append([
            "KII", record.kii_id, organisation_name(record), token.channel, _when(token.issued_at),
            kii_issued.get(str(token.pk), (None, ""))[1], token.status, _day(token.expires_at),
            _when(kii_emailed.get(str(token.pk), (None, None))[0]), _when(token.revoked_at), token.revoked_reason,
        ])
    log_rows.sort(key=lambda row: row[4])

    wb = Workbook()
    _sheet(wb, "Main-400 respondents", main_columns, main_rows, first=True)
    _sheet(wb, "KII informants", kii_columns, kii_rows)
    _sheet(wb, "Invitation log", log_columns, log_rows)
    notes = wb.create_sheet("About this file")
    for line in (
        f"ABF-FST respondents and outreach, generated {_when(timezone.now())}.",
        "Contains names and contact details: internal use by the research team only. Store on encrypted, "
        "access-controlled storage and never share outside the team.",
        "Main-400 respondents: one row per person on a contactable case (a case with nobody recorded yet still has a row).",
        "A WhatsApp invitation is recorded when it is created. WhatsApp does not tell the portal whether it was sent, "
        "delivered or read; the status column shows when the respondent opened the link.",
        "'Reminders recorded as sent' counts only reminders marked as sent on the Follow-ups screen.",
        "A status of EXPIRED includes invitations replaced by a newer one for the same case.",
    ):
        notes.append([line])
    notes.column_dimensions["A"].width = 120

    out = BytesIO()
    wb.save(out)
    counts = {"cases": len(cases), "people": people, "kii_records": len(kii_records), "invitations": len(log_rows)}
    return out.getvalue(), counts
