"""Automatic Reserve replacement (PI decision, 2026-10-12).

When the PI has switched it on (ReplacementPolicy), the 08:00 run activates the paired Reserve of every Main case that
did not take part and introduces the Reserve on WhatsApp ("ask first", apps/messaging/outreach.py): a YES sends its
invitation link automatically, as for Main cases.

"Did not take part" is whichever of these the PI ticked, each recorded under its authorised reason:

    Refused (S12)                         -> Refusal
    Nonresponse exhausted (S13)           -> Nonresponse exhausted
    No reply to the introduction          -> Nonresponse exhausted (the Main case moves S03/S04 -> S13 first)
    Ineligible (S14)                      -> Ineligible
    Duplicate/inactive (S15)              -> Inactive (S15 does not say which; the evidence note says both)

AGENTS.md rule 4 still holds: every activation goes through activate_reserve() with an authorised reason, an evidence
note saying what happened, and an AuditEvent -- and the authoriser is the PI who switched the policy on, the standing
authorisation that replaces approving each case. Only the Main case's own paired Reserve is ever activated, and only
while it is LOCKED, so one activation can never stand for two Main cases.

The replaced Main case keeps its outcome (S12-S15), so refusal and nonresponse rates stay right; its open invitation
links are revoked, so the sample can never reach 401. A Reserve that itself refuses or never answers is not replaced
again: each Main case has exactly one Reserve.
"""

import logging

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from apps.audit.utils import log_action

from .models import (
    ActivationReason,
    ReplacementPolicy,
    ReplacementTrigger,
    ReserveStatus,
    SampleCase,
    SampleType,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

TRIGGER_STATUS = {
    ReplacementTrigger.REFUSED: WorkflowStatus.S12_REFUSED,
    ReplacementTrigger.NONRESPONSE: WorkflowStatus.S13_NONRESPONSE,
    ReplacementTrigger.INELIGIBLE: WorkflowStatus.S14_INELIGIBLE,
    ReplacementTrigger.DUPLICATE_INACTIVE: WorkflowStatus.S15_DUPLICATE_INACTIVE,
}
TRIGGER_REASON = {
    ReplacementTrigger.REFUSED: ActivationReason.REFUSAL,
    ReplacementTrigger.NONRESPONSE: ActivationReason.NONRESPONSE_EXHAUSTED,
    ReplacementTrigger.NO_REPLY: ActivationReason.NONRESPONSE_EXHAUSTED,
    ReplacementTrigger.INELIGIBLE: ActivationReason.INELIGIBLE,
    ReplacementTrigger.DUPLICATE_INACTIVE: ActivationReason.INACTIVE,
}
NO_REPLY_FROM = [WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED, WorkflowStatus.S04_INVITATION_PREPARED]
# The key on an automatically activated Reserve's metadata: which Main case it replaced, why, and when.
META_KEY = "auto_replacement"


def _latest_outreach_status():
    from apps.messaging.models import Outreach

    return Subquery(Outreach.objects.filter(sample_case=OuterRef("pk")).order_by("-intro_sent_at").values("status")[:1])


def due(policy: ReplacementPolicy) -> list[tuple[SampleCase, str]]:
    """(Main case, trigger) for every Main case the policy says to replace now, oldest first."""
    from apps.messaging.models import OutreachStatus

    triggers = [t for t in policy.triggers if t in ReplacementTrigger.values]
    statuses = {TRIGGER_STATUS[t]: t for t in triggers if t in TRIGGER_STATUS}
    wanted = Q(workflow_status__in=list(statuses))
    if ReplacementTrigger.NO_REPLY in triggers:
        wanted |= Q(workflow_status__in=NO_REPLY_FROM, latest_outreach=OutreachStatus.NO_REPLY)
    cases = (SampleCase.objects.filter(sample_type=SampleType.MAIN, matched_case__sample_type=SampleType.RESERVE,
                                       matched_case__status=ReserveStatus.LOCKED)
             .annotate(latest_outreach=_latest_outreach_status()).filter(wanted)
             .select_related("matched_case", "organisation").order_by("updated_at", "sample_id"))
    return [(case, statuses.get(case.workflow_status, ReplacementTrigger.NO_REPLY)) for case in cases]


def _what_happened(case: SampleCase, trigger: str) -> str:
    from apps.messaging.models import Outreach, OutreachStatus

    outreach = Outreach.objects.filter(sample_case=case).order_by("-intro_sent_at").first()
    asked = f"{timezone.localtime(outreach.intro_sent_at):%d %b %Y}" if outreach else ""
    if trigger == ReplacementTrigger.REFUSED:
        if outreach and outreach.status == OutreachStatus.DECLINED and outreach.replied_at:
            return f"said no to the study's introduction on {timezone.localtime(outreach.replied_at):%d %b %Y}"
        return "was recorded as Refused (S12)"
    if trigger == ReplacementTrigger.NO_REPLY:
        return f"did not reply to the introduction sent on {asked} or to its reminder"
    if trigger == ReplacementTrigger.NONRESPONSE:
        return "did not respond after the invitation and every reminder (Nonresponse, S13)"
    if trigger == ReplacementTrigger.INELIGIBLE:
        return "was found ineligible (S14)"
    return "was found to be a duplicate or inactive (S15)"


def replace(case: SampleCase, trigger: str, policy: ReplacementPolicy) -> SampleCase | None:
    """Activate this Main case's own Reserve. Returns the Reserve, or None if it was not (already activated, no pair)."""
    from apps.invitations.models import InvitationToken, TokenStatus
    from apps.invitations.services import revoke_token

    from .services import activate_reserve, transition_workflow_status

    with transaction.atomic():
        case = SampleCase.objects.select_for_update().get(pk=case.pk)
        if case.matched_case_id is None:
            return None
        reserve = SampleCase.objects.select_for_update().get(pk=case.matched_case_id)
        if reserve.sample_type != SampleType.RESERVE or reserve.status != ReserveStatus.LOCKED:
            return None
        if trigger == ReplacementTrigger.NO_REPLY:
            transition_workflow_status(case, WorkflowStatus.S13_NONRESPONSE)
        for token in InvitationToken.objects.filter(sample_case=case).exclude(
                status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED]):
            revoke_token(token, f"Replaced by Reserve {reserve.sample_id}")
        authoriser = policy.enabled_by
        note = (f"Automatic replacement: {case.sample_id} ({case.organisation.name}) {_what_happened(case, trigger)}. "
                f"Activated under the standing authorisation {authoriser.get_full_name() or authoriser.username} gave on "
                f"{timezone.localtime(policy.enabled_at):%d %b %Y}.")
        activate_reserve(reserve, reason=TRIGGER_REASON[trigger], activated_by=authoriser, evidence_note=note,
                         audit_extra={"automatic": True, "replaces": case.sample_id, "trigger": trigger})
        reserve.assigned_ra_id = case.assigned_ra_id
        reserve.metadata = {**(reserve.metadata or {}), META_KEY: {
            "replaces": case.sample_id, "trigger": trigger, "at": timezone.now().isoformat(), "contact_note": "",
        }}
        reserve.save(update_fields=["assigned_ra", "metadata", "updated_at"])
    return reserve


def _activated_today() -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return SampleCase.objects.filter(sample_type=SampleType.RESERVE, activated_at__gte=start,
                                     metadata__has_key=META_KEY).count()


def introduce_replacements() -> dict:
    """Introduce on WhatsApp every automatically activated Reserve not yet introduced. One that can't be (templates not
    approved yet, today's limit, no mobile) is tried again the next morning; why is kept for the Reserve screen."""
    from apps.messaging.outreach import OutreachError, introduction_candidates, send_introduction

    introduced, waiting = 0, 0
    pending = SampleCase.objects.filter(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED, metadata__has_key=META_KEY)
    ready = set(introduction_candidates().filter(pk__in=pending.values("pk")).values_list("pk", flat=True))
    for reserve in pending.exclude(outreaches__isnull=False).order_by("activated_at"):
        note = ""
        if reserve.pk not in ready:
            note = "No mobile number on record: find contact details, then send the introduction or an invitation."
        else:
            try:
                send_introduction(reserve, user=None)
                introduced += 1
            except OutreachError as exc:
                note = str(exc)
                if exc.code == "daily_limit_reached":
                    break
        if note:
            waiting += 1
            meta = reserve.metadata or {}
            if meta.get(META_KEY, {}).get("contact_note") != note:
                reserve.metadata = {**meta, META_KEY: {**meta.get(META_KEY, {}), "contact_note": note}}
                reserve.save(update_fields=["metadata", "updated_at"])
    return {"introduced": introduced, "waiting": waiting}


def run_auto_replacement() -> dict:
    """The morning run. Does nothing while the policy is off."""
    policy = ReplacementPolicy.current()
    if not policy.enabled or policy.enabled_by_id is None:
        return {"skipped": "automatic replacement is off"}
    left = max(0, policy.daily_max - _activated_today())
    activated = []
    for case, trigger in due(policy)[:left]:
        try:
            reserve = replace(case, trigger, policy)
        except Exception:  # noqa: BLE001 -- one case that can't be replaced must not stop the others
            logger.exception("Automatic replacement of %s failed", case.sample_id)
            continue
        if reserve is not None:
            activated.append(f"{case.sample_id}->{reserve.sample_id}")
    contact = introduce_replacements()
    if activated:
        log_action("reserve.auto_replacement_run", policy, {"activated": activated, **contact})
    return {"activated": activated, **contact}
