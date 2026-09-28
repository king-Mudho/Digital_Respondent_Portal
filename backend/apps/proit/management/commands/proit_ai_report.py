"""Read-only summary of how the AI desk research has been used and how researchers judged it: runs, searches, how
many proposed facts were accepted, accepted with edits, rejected, or not found publicly, and the confidence levels.
For the ethics and methodology write-up (how accurate was the AI, and did people check it). Changes nothing.

Run: manage.py proit_ai_report"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from apps.proit.models import AIProposal, AIProposalStatus, AIResearchRun


def report() -> dict:
    runs = AIResearchRun.objects.all()
    by_status = dict(AIProposal.objects.values_list("status").annotate(n=Count("id")))
    decided = sum(by_status.get(s, 0) for s in (AIProposalStatus.ACCEPTED, AIProposalStatus.EDITED, AIProposalStatus.REJECTED))
    accepted = by_status.get(AIProposalStatus.ACCEPTED, 0) + by_status.get(AIProposalStatus.EDITED, 0)
    sums = runs.aggregate(searches=Sum("searches_used"), tokens_in=Sum("tokens_in"), tokens_out=Sum("tokens_out"))
    return {
        "runs": {s: n for s, n in runs.values_list("status").annotate(n=Count("id"))},
        "organisations_researched": runs.values("pre_profile").distinct().count(),
        "searches": sums["searches"] or 0, "tokens_in": sums["tokens_in"] or 0, "tokens_out": sums["tokens_out"] or 0,
        "proposals": by_status,
        "decided": decided,
        "accepted_share": (accepted / decided) if decided else None,
        "edited_share_of_accepted": (by_status.get(AIProposalStatus.EDITED, 0) / accepted) if accepted else None,
        "confidence": dict(AIProposal.objects.exclude(confidence="").values_list("confidence").annotate(n=Count("id"))),
        "dropped_by_server": sum(len(d) for d in runs.values_list("dropped", flat=True) if d),
    }


class Command(BaseCommand):
    help = "Read-only summary of AI desk-research use and researcher decisions."

    def handle(self, *args, **opts):
        r = report()
        w = self.stdout.write
        w(f"Organisations researched: {r['organisations_researched']}  |  runs: {r['runs'] or 'none'}")
        w(f"Web searches: {r['searches']}  |  tokens in/out: {r['tokens_in']:,} / {r['tokens_out']:,}")
        w("Proposals by outcome: " + (", ".join(f"{k} {v}" for k, v in sorted(r["proposals"].items())) or "none"))
        if r["decided"]:
            w(f"Decided by a researcher: {r['decided']}  |  accepted (with or without edits): {r['accepted_share']:.0%}"
              + (f"  |  of those, edited first: {r['edited_share_of_accepted']:.0%}" if r["edited_share_of_accepted"] is not None else ""))
        else:
            w("No proposal has been accepted or rejected yet.")
        w("Confidence: " + (", ".join(f"{k} {v}" for k, v in sorted(r["confidence"].items())) or "none"))
        w(f"Findings the server removed as unverifiable or private: {r['dropped_by_server']}")
