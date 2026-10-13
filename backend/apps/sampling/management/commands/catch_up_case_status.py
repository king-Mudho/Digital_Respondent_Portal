"""manage.py catch_up_case_status [--apply]

Brings every verified Main case (S03-S08) up to what its respondent has already done, using
sampling.services.catch_up_respondent_path() -- the same step that now runs whenever a case is marked verified.

Written for the cases found on 2026-10-12: organisations registered by hand, invited while still at S00, then moved to
S03 by bulk verification, so they sat at S03 holding sent, opened and QA-passed links. Without --apply it only lists
what would change. Cases still below S03 are listed but never moved: verification is a researcher's decision. Each
case moved is audited as sampling.status_caught_up.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.invitations.models import InvitationToken
from apps.sampling.models import SampleCase, SampleType
from apps.sampling.services import RESPONDENT_PATH, catch_up_respondent_path


class Command(BaseCommand):
    help = "Bring verified Main cases up to what their respondents have already done (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Make the changes (default: only list them).")

    def handle(self, *args, apply=False, **options):
        invited = SampleCase.objects.filter(sample_type=SampleType.MAIN, invitation_tokens__isnull=False).distinct()
        moved, unverified = 0, []
        for case in invited.order_by("sample_id"):
            if case.workflow_status not in RESPONDENT_PATH:
                if case.workflow_status in ("S00", "S01", "S02"):
                    unverified.append(case)
                continue
            before = case.workflow_status
            with transaction.atomic():
                catch_up_respondent_path(case)
                after = case.workflow_status
                if not apply:
                    transaction.set_rollback(True)
            if after != before:
                moved += 1
                self.stdout.write(f"{case.sample_id} {case.organisation.name}: {before} -> {after}")
        verb = "Moved" if apply else "Would move"
        self.stdout.write(self.style.SUCCESS(f"{verb} {moved} case(s)."))
        if unverified:
            self.stdout.write(f"{len(unverified)} invited case(s) are not verified yet and were left alone (a researcher "
                              "verifies them on the register; their status then catches up automatically):")
            for case in unverified:
                furthest = ", ".join(sorted(set(InvitationToken.objects.filter(sample_case=case).values_list("status", flat=True))))
                self.stdout.write(f"  {case.sample_id} {case.organisation.name} ({case.workflow_status}; links: {furthest})")
