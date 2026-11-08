"""manage.py renew_invitation_links [--apply] [--within-days N]

Renews the links of people on a Research Assistant's call list that have expired or will soon (invitations.renewal):
the link the person already has works again, and nothing is sent. Without --apply it only lists what it would do. The
same runs every night at 05:30 while INVITATION_AUTO_RENEW is on; every renewed link gets an audit entry."""

from django.core.management.base import BaseCommand

from apps.invitations.renewal import renew_call_list_links


class Command(BaseCommand):
    help = "Renew expired or expiring links on the Research Assistants' call lists (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Make the change. Without it, nothing is written.")
        parser.add_argument("--within-days", type=float, default=None,
                            help="Also renew links due to run out within this many days (default: the setting).")

    def handle(self, *args, apply=False, within_days=None, **options):
        result = renew_call_list_links(apply=apply, within_days=within_days)
        verb = "Renewed" if apply else "Would renew"
        for e in result["renewed"]:
            state = "expired" if e["expired"] else "running out"
            self.stdout.write(f"{verb} {e['id']} {e['channel']} link ({state} {e['was']:%d %b %Y})")
        for e in result["skipped"]:
            self.stdout.write(f"Left {e['id']} {e['channel']} link as it is: {e['why']}")
        main = sum(1 for e in result["renewed"] if e["kind"] == "main")
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {main} Main-400 and {len(result['renewed']) - main} KII links, now valid until "
            f"{result['new_expiry']:%d %b %Y}; left {len(result['skipped'])} as they are."
            + ("" if apply else " Nothing was changed: run again with --apply.")))
