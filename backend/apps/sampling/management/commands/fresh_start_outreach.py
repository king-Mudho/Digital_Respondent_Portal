"""manage.py fresh_start_outreach --reason "..." [--apply]

Starts Main-400 outreach afresh (PI decision, 2026-10-14): the study now sends from a new WhatsApp line, and the PI
wants every case that was contacted but never completed to be asked again from the beginning -- "ask first", then the
link -- instead of being reminded about an old invitation.

A case is reset when it is a Main case that was invited or further (S04-S09) or marked Nonresponse (S13), and has no
questionnaire submission. Each such case:

- has every link it still holds revoked (so no reminder about an old link goes out, and nothing old can be submitted);
- goes back to S03 (eligible respondent identified), ready for an introduction or a new invitation;
- is audited as sampling.status_reset_fresh_start, with the reason and the links revoked.

Nothing else changes: respondents, consent records (a consent given stays given; a decline stays on file and the
consent page asks again), messages and the audit trail are kept. Cases with a submission, refusals (S12), unverified
cases (S00-S02) and Reserve cases are never touched. Without --apply it only lists what would change.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.audit.utils import log_action
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import revoke_token
from apps.kobo.models import QUANSubmission
from apps.sampling.models import SampleCase, SampleType

RESETTABLE = ["S04", "S05", "S06", "S07", "S08", "S09", "S13"]
FINAL_TOKENS = [TokenStatus.EXPIRED, TokenStatus.REVOKED]


def fresh_start_cases():
    submitted = QUANSubmission.objects.filter(sample_case=OuterRef("pk"))
    return (SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status__in=RESETTABLE)
            .exclude(Exists(submitted)).order_by("sample_id"))


def reset_case(case, *, reason: str, user=None) -> int:
    """Revoke the case's remaining links and return it to S03. Returns how many links were revoked."""
    revoked = 0
    for token in InvitationToken.objects.filter(sample_case=case).exclude(status__in=FINAL_TOKENS):
        revoke_token(token, f"Fresh start: {reason}", revoked_by=user)
        revoked += 1
    before = case.workflow_status
    SampleCase.objects.filter(pk=case.pk).update(workflow_status="S03")
    case.workflow_status = "S03"
    log_action("sampling.status_reset_fresh_start", case, {
        "sample_id": case.sample_id, "from": before, "to": "S03", "reason": reason, "links_revoked": revoked,
        "user_id": getattr(user, "id", None),
    }, user=user)
    return revoked


class Command(BaseCommand):
    help = "Return contacted-but-not-completed Main cases to S03 for a fresh start (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--reason", required=True, help="Why, as it should read in the audit log.")
        parser.add_argument("--user", default="", help="Username of the person authorising it (recorded in the audit log).")
        parser.add_argument("--apply", action="store_true", help="Make the changes (default: only list them).")

    def handle(self, *args, reason, user="", apply=False, **options):
        from apps.accounts.models import User

        reason = reason.strip()
        if len(reason) < 10:
            raise CommandError("Give a real reason (it is written to every case's audit entry).")
        who = User.objects.filter(username=user).first() if user else None
        if user and who is None:
            raise CommandError(f"No user called {user!r}.")
        cases = list(fresh_start_cases())
        by_status = {}
        for case in cases:
            by_status[case.workflow_status] = by_status.get(case.workflow_status, 0) + 1
        links = InvitationToken.objects.filter(sample_case__in=cases).exclude(status__in=FINAL_TOKENS).count()
        self.stdout.write(f"{len(cases)} cases would return to S03 {by_status}; {links} links would be revoked.")
        if not apply:
            self.stdout.write("Dry run: nothing changed. Add --apply to do it.")
            return
        with transaction.atomic():
            revoked = sum(reset_case(case, reason=reason, user=who) for case in cases)
        self.stdout.write(self.style.SUCCESS(f"Reset {len(cases)} cases to S03; revoked {revoked} links."))
