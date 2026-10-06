"""manage.py reopen_superseded_invitations [--apply]

Switches back on the invitation links that were replaced by a second invitation and are still within their dates
(services.reopen_superseded_invitations). Without --apply it only lists what it would do. Take a backup first
(deploy/backup.sh); every reopened link gets an invitation.reopened audit entry."""

from django.core.management.base import BaseCommand

from apps.invitations.services import reopen_superseded_invitations


class Command(BaseCommand):
    help = "Reopen invitation links replaced by a newer invitation that is still waiting (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Make the change. Without it, nothing is written.")

    def handle(self, *args, apply=False, **options):
        result = reopen_superseded_invitations(apply=apply)
        verb = "Reopened" if apply else "Would reopen"
        for entry in result["reopened"]:
            self.stdout.write(f"{verb} {entry['sample_id']} {entry['channel']} link (valid until "
                              f"{entry['expires_at']:%d %b %Y}; newer invitation {entry['newest_status']})")
        for entry in result["skipped"]:
            self.stdout.write(f"Left closed {entry['sample_id']} {entry['channel']} link: newer invitation is "
                              f"{entry['newest_status']}")
        cases = len({e["sample_id"] for e in result["reopened"]})
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {len(result['reopened'])} links on {cases} cases; left {len(result['skipped'])} closed."
            + ("" if apply else " Nothing was changed: run again with --apply.")))
