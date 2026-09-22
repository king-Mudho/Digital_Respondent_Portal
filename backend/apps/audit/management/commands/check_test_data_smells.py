"""Flags likely test/pilot data on production, using the same patterns found and cleaned up by hand on
2026-09-22 (see docs/ manuals changelog): an empty pre-interview profile stub, a KII or respondent contact
whose name/email matches a staff account, a case that moved from invited to QA-passed implausibly fast for
real fieldwork, a document with an uploaded file sitting unsubmitted, and an audit event whose own metadata
names a user but whose `user` field is still blank (a residual instance of the gap fixed in apps/audit/utils.py).

Never deletes or changes anything -- read-only. A human decides what, if anything, to act on, the same way
the 2026-09-22 cleanup was scoped and confirmed step by step before anything was touched.

Run: manage.py check_test_data_smells [--since YYYY-MM-DD]
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentRecord
from apps.contacts.models import Respondent
from apps.evidence.models import DocumentRecord
from apps.invitations.models import InvitationToken
from apps.kii.models import KIIRecord
from apps.proit.models import PreProfile

FAST_TURNAROUND = timedelta(hours=2)  # real fieldwork (invite -> consent -> submit -> QA) never happens this fast


class Command(BaseCommand):
    help = "Read-only scan for likely test/pilot data left on production (see module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--since", help="Only consider records created/changed on or after this date (YYYY-MM-DD).")

    def handle(self, *args, since=None, **opts):
        cutoff = parse_date(since) if since else None
        found = 0
        found += self._empty_preprofiles(cutoff)
        found += self._staff_named_contacts()
        found += self._fast_turnaround_cases(cutoff)
        found += self._stale_uploaded_documents(cutoff)
        found += self._unattributed_audit_events(cutoff)
        self.stdout.write(self.style.SUCCESS(f"\n{found} item(s) flagged for a human to look at. Nothing was changed."))

    def _hdr(self, title):
        self.stdout.write(self.style.WARNING(f"\n-- {title} --"))

    # 1. A pre-interview profile with no fields and never locked -- someone opened PROIT on a case and
    #    didn't (or hasn't yet) put anything on it. Could be abandoned test activity, or just started.
    def _empty_preprofiles(self, cutoff):
        qs = PreProfile.objects.filter(prepopulation_locked_at__isnull=True, fields__isnull=True)
        if cutoff:
            qs = qs.filter(created_at__date__gte=cutoff)
        rows = list(qs.select_related("sample_case", "kii_record"))
        if not rows:
            return 0
        self._hdr(f"Empty, unlocked pre-interview profiles ({len(rows)})")
        for p in rows:
            who = p.sample_case.sample_id if p.sample_case_id else p.kii_record.kii_id
            self.stdout.write(f"  PreProfile #{p.id} on {who}, created {p.created_at:%Y-%m-%d %H:%M}")
        return len(rows)

    # 2. A KII or respondent contact whose name or email matches a staff account -- the "Happyson Saina"
    #    pattern found on KII-0068/KII-0083.
    def _staff_named_contacts(self):
        staff = {(u.get_full_name() or "").strip().lower(): u.username for u in User.objects.all() if u.get_full_name()}
        staff_emails = {u.email.lower(): u.username for u in User.objects.exclude(email="")}
        hits = []
        for k in KIIRecord.objects.exclude(participant_name=""):
            name = k.participant_name.strip().lower()
            if name in staff:
                hits.append(f"KII {k.kii_id}: participant_name matches staff account '{staff[name]}'")
        for r in Respondent.objects.exclude(email=""):
            email = r.email.strip().lower()
            if email in staff_emails:
                hits.append(f"Respondent #{r.id} (case {r.sample_case.sample_id}): email matches staff account '{staff_emails[email]}'")
        if not hits:
            return 0
        self._hdr(f"Contacts that look like a staff member's own details ({len(hits)})")
        for h in hits:
            self.stdout.write(f"  {h}")
        return len(hits)

    # 3. A case that went from invitation issued to QA-passed faster than real fieldwork ever does --
    #    the signature of someone clicking through the whole flow themselves to try it out (SID-2026-000062).
    def _fast_turnaround_cases(self, cutoff):
        from apps.kobo.models import QUANSubmission

        hits = []
        qs = QUANSubmission.objects.filter(qa_status="QA_PASSED").select_related("sample_case")
        if cutoff:
            qs = qs.filter(submitted_at__date__gte=cutoff)
        for s in qs:
            invite = InvitationToken.objects.filter(sample_case=s.sample_case).order_by("issued_at").first()
            if invite and s.submitted_at and (s.submitted_at - invite.issued_at) < FAST_TURNAROUND:
                hits.append(f"{s.sample_case.sample_id}: invited {invite.issued_at:%Y-%m-%d %H:%M}, submitted {s.submitted_at:%Y-%m-%d %H:%M} "
                            f"({(s.submitted_at - invite.issued_at)} later)")
        if not hits:
            return 0
        self._hdr(f"Cases completed implausibly fast for real fieldwork ({len(hits)})")
        for h in hits:
            self.stdout.write(f"  {h}")
        return len(hits)

    # 4. A document with an uploaded file and/or AI draft sitting there a while, never submitted -- worth
    #    a human glance (DOC-0001/DOC-0007's test uploads looked exactly like this).
    def _stale_uploaded_documents(self, cutoff):
        qs = DocumentRecord.objects.exclude(source_file_ref="").filter(kobo_submitted_at__isnull=True)
        if cutoff:
            qs = qs.filter(source_file_uploaded_at__date__gte=cutoff)
        old = [d for d in qs if d.source_file_uploaded_at and timezone.now() - d.source_file_uploaded_at > timedelta(days=3)]
        if not old:
            return 0
        self._hdr(f"Documents with a file uploaded 3+ days ago, still not submitted ({len(old)})")
        for d in old:
            self.stdout.write(f"  {d.document_id} {d.title!r}: uploaded {d.source_file_uploaded_at:%Y-%m-%d}")
        return len(old)

    # 5. An audit event whose own metadata names a user, but whose `user` field is still blank -- a
    #    residual instance of the gap fixed in apps/audit/utils.py (2026-09-22), in case another call
    #    site still has it.
    def _unattributed_audit_events(self, cutoff):
        qs = AuditEvent.objects.filter(user__isnull=True)
        if cutoff:
            qs = qs.filter(created_at__date__gte=cutoff)
        hits = []
        for e in qs:
            uid = (e.metadata or {}).get("user_id") or (e.metadata or {}).get("issued_by_id") or (e.metadata or {}).get("by_user_id")
            if uid and User.objects.filter(id=uid).exists():
                hits.append(f"AuditEvent #{e.id} ({e.action}, {e.created_at:%Y-%m-%d}): metadata names user {uid} but user field is blank")
        if not hits:
            return 0
        self._hdr(f"Audit events with a named user but no attribution ({len(hits)})")
        for h in hits:
            self.stdout.write(f"  {h}")
        return len(hits)
