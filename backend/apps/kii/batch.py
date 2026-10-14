"""Batch KII invitations (PI request, 2026-10-13): the PI or Field Coordinator chooses how many KII records, and each
gets its own self-service link by email -- and by WhatsApp or SMS through Twilio -- as the Main-400 batch does.

There is no separate sending path: each record goes through issue_kii_invitation() (which supersedes any older link
and moves PROSPECT to INVITED), then email_kii_invitation() and text_kii_invitation() -- the approved wording and the
audit entries -- exactly as the record's own Send buttons do. Only records never invited (PROSPECT) with no open link
and a contact for a chosen channel are candidates, from the register groups the sender picks, Core-60 first.

One link per record, sent on every chosen channel it can receive, issued and sent as ONE database transaction: if no
channel gets through, the link and the move to INVITED are undone together, so a record never shows "Invited" for a
message that never left. Batches are InvitationBatch rows with mode "KII", sharing the Main-400 caps -- one batch at a
time and one daily email limit for the study mailbox (AGENTS.md rule 7) -- and recording masked addresses only.

"Ask first" (2026-10-14): a batch with options["intro"] sends each record the KII introduction instead
(apps/messaging/outreach.send_kii_introduction); a YES on WhatsApp then issues and sends the link by itself.
"""

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.utils import timezone

from apps.audit.utils import log_action
from apps.invitations import batch as main
from apps.invitations.batch import BatchError, NothingSent
from apps.invitations.messages import portal_base
from apps.invitations.models import InvitationBatch, InvitationBatchStatus

from .messages import KIIInvitationSendError, _mask, email_kii_invitation, kii_recipients, text_kii_invitation
from .models import KIIInvitationToken, KIIInvitationTokenStatus, KIIRecord, KIIStatus
from .services import issue_kii_invitation

logger = logging.getLogger(__name__)

MODE = "KII"
# The register's groups, in the order they are invited: metadata["pool"] as import_kii_register set it, and ADDITIONAL
# for the organisations registered from a list on 13 Oct (and any record added by hand, which carries no pool).
GROUPS = ("CORE_60", "RESERVE_30", "ADDITIONAL")
GROUP_LABEL = {"CORE_60": "Core-60", "RESERVE_30": "Reserve-30", "ADDITIONAL": "Additional organisations"}
OPEN_STATUSES = [
    KIIInvitationTokenStatus.GENERATED, KIIInvitationTokenStatus.SENT, KIIInvitationTokenStatus.OPENED,
    KIIInvitationTokenStatus.CONSENTED, KIIInvitationTokenStatus.STARTED,
]


def clean_groups(groups) -> list[str]:
    chosen = [group for group in GROUPS if group in (groups or [])]
    if not chosen:
        raise BatchError("no_group", "Choose at least one group: Core-60, Reserve-30 or Additional organisations.")
    return chosen


def _in_groups(groups) -> Q:
    q = Q(metadata__pool__in=list(groups))
    if "ADDITIONAL" in groups:
        q |= ~Q(metadata__has_key="pool")
    return q


def candidates(channels=("EMAIL",), groups=GROUPS, *, named_only: bool = False):
    """Records never invited, in the chosen groups, with a contact for at least one of `channels` and no open link.
    Whether a number is a mobile is decided per record by kii_recipients()."""
    reachable = Q(pk__in=[])
    if "EMAIL" in channels:
        reachable |= ~Q(email="")
    if "SMS" in channels or "WHATSAPP" in channels:
        reachable |= ~Q(phone="") | ~Q(whatsapp_number="")
    open_link = KIIInvitationToken.objects.filter(kii_record=OuterRef("pk"), status__in=OPEN_STATUSES, expires_at__gt=timezone.now())
    records = (
        KIIRecord.objects.filter(status=KIIStatus.PROSPECT).filter(_in_groups(groups)).filter(reachable)
        .exclude(Exists(open_link))
    )
    if named_only:
        from apps.contacts.kii_finder import PLACEHOLDER_SUFFIX

        records = records.exclude(participant_name__iendswith=PLACEHOLDER_SUFFIX)
    order = Case(*[When(metadata__pool=group, then=Value(i)) for i, group in enumerate(GROUPS)],
                 default=Value(len(GROUPS)), output_field=IntegerField())
    return records.annotate(group_order=order).order_by("group_order", "kii_id")


def reachable_channels(record, channels) -> list[str]:
    who = kii_recipients(record)
    return [channel for channel in channels if who[main.RECIPIENT_FIELD[channel]]]


def channel_configured(channel: str) -> bool:
    from apps.messaging import twilio_client as tw

    if channel == "WHATSAPP":
        return tw.whatsapp_configured(kii=True)
    return main.channel_configured(channel)


def group_of(record) -> str:
    pool = (record.metadata or {}).get("pool")
    return pool if pool in GROUPS else "ADDITIONAL"


def summary(channels=("EMAIL",), groups=GROUPS, *, named_only: bool = False) -> dict:
    """What a batch with these choices would do now, and per channel and group what is ready."""
    from apps.contacts.kii_finder import is_placeholder, organisation_name
    from apps.messaging import twilio_client as tw

    everyone = list(candidates(main.CHANNELS, GROUPS))
    chosen = list(candidates(channels, groups, named_only=named_only))
    preview = []
    for record in chosen[:10]:
        who = kii_recipients(record)
        mobile = who["sms_to"] or who["whatsapp_to"]
        preview.append({
            "kii_id": record.kii_id, "organisation": organisation_name(record),
            "informant": "" if is_placeholder(record) else record.participant_name, "group": GROUP_LABEL[group_of(record)],
            "email": _mask(who["email_to"]) if who["email_to"] else "", "mobile": tw.mask(mobile) if mobile else "",
            "channels": reachable_channels(record, channels),
        })
    approvals = tw.template_approvals()
    return {
        "candidates": len(chosen),
        "unnamed": sum(1 for record in chosen if is_placeholder(record)),
        "preview": preview,
        "groups": {group: sum(1 for record in everyone if group_of(record) == group) for group in GROUPS},
        "channels": {
            channel: {
                "configured": channel_configured(channel),
                "ready": sum(1 for record in everyone if reachable_channels(record, (channel,))),
                "left_today": main.channel_left_today(channel), "daily_max": main.channel_daily_max(channel),
                **({"template_waiting": tw.template_waiting("TWILIO_WA_CONTENT_KII_INVITATION", approvals=approvals)}
                   if channel == "WHATSAPP" else {}),
            }
            for channel in main.CHANNELS
        },
        "max_per_batch": main.per_batch_max(),
        "introductions": introduction_summary(groups, named_only=named_only),
    }


def introduction_summary(groups=GROUPS, *, named_only: bool = False) -> dict:
    """For "Ask first": set up or not, how it would go out, and how many records could be introduced."""
    from apps.messaging import outbound, outreach
    from apps.messaging import twilio_client as tw

    channel = outreach.intro_channel(kii=True)
    ready = [r for r in outreach.kii_introduction_candidates(groups, named_only=named_only)
             if reachable_channels(r, ("WHATSAPP",)) and not outreach.tried_this_number(r)]
    waiting = tw.template_waiting("TWILIO_WA_CONTENT_KII_INTRO")
    return {"configured": channel is not None, "channel": channel or "", "ready": len(ready),
            "left_today": outbound.left_today(channel) if channel else 0, "template_waiting": waiting,
            "template_set": bool((settings.TWILIO_WA_CONTENT_KII_INTRO or "").strip())}


def start_batch(limit: int, *, user, channels=("EMAIL",), groups=GROUPS, named_only: bool = False,
                intro: bool = False) -> InvitationBatch:
    if intro:
        return _start_intro_batch(limit, user=user, groups=clean_groups(groups), named_only=named_only)
    channels, groups = main.clean_channels(channels), clean_groups(groups)
    for channel in channels:
        if not channel_configured(channel):
            how = "deploy/configure-email.sh" if channel == "EMAIL" else "deploy/configure-twilio.sh"
            label = main.CHANNEL_LABEL[channel][:1].upper() + main.CHANNEL_LABEL[channel][1:]
            raise BatchError(f"{channel.lower()}_not_configured", f"{label} isn't set up on the server yet. Run {how} first.", 503)
    if "WHATSAPP" in channels:
        main.refuse_unapproved_whatsapp("TWILIO_WA_CONTENT_KII_INVITATION", "KII invitation")
    allowed = min([main.per_batch_max()] + [main.channel_left_today(channel) for channel in channels])
    if allowed < 1:
        raise BatchError("daily_limit_reached", "Today's sending limit has been reached for a chosen channel. Try again tomorrow.", 409)
    if not 1 <= limit <= allowed:
        raise BatchError("bad_limit", f"Choose between 1 and {allowed} invitations.")
    if InvitationBatch.objects.filter(status=InvitationBatchStatus.RUNNING, started_at__gte=timezone.now() - timedelta(hours=1)).exists():
        raise BatchError("already_running", "A batch is already sending. Wait for it to finish.", 409)
    batch = InvitationBatch.objects.create(created_by=user, requested=limit, channels=channels, mode=MODE,
                                           options={"groups": groups, "named_only": named_only})
    log_action("kii_invitations.batch_started", batch, {"requested": limit, "channels": channels, "groups": groups,
                                                        "named_only": named_only, "user_id": getattr(user, "id", None)}, user=user)
    return batch


def _start_intro_batch(limit: int, *, user, groups, named_only: bool) -> InvitationBatch:
    info = introduction_summary(groups, named_only=named_only)
    if not info["configured"]:
        raise BatchError("intro_not_configured", "KII introductions aren't set up yet: they need the study's WhatsApp number "
                                                 "and the KII introduction template on Twilio (deploy/configure-twilio.sh).", 503)
    allowed = min(main.per_batch_max(), info["left_today"])
    if allowed < 1:
        raise BatchError("daily_limit_reached", "Today's sending limit has been reached. Try again tomorrow.", 409)
    if not 1 <= limit <= allowed:
        raise BatchError("bad_limit", f"Choose between 1 and {allowed} introductions.")
    if InvitationBatch.objects.filter(status=InvitationBatchStatus.RUNNING, started_at__gte=timezone.now() - timedelta(hours=1)).exists():
        raise BatchError("already_running", "A batch is already sending. Wait for it to finish.", 409)
    batch = InvitationBatch.objects.create(created_by=user, requested=limit, channels=[info["channel"]], mode=MODE,
                                           options={"groups": groups, "named_only": named_only, "intro": True})
    log_action("kii_invitations.batch_started", batch, {"requested": limit, "intro": True, "groups": groups,
                                                        "named_only": named_only, "user_id": getattr(user, "id", None)}, user=user)
    return batch


def _run_intro_batch(batch, options) -> list[dict]:
    """Send the KII introduction to `batch.requested` records. One record failing never stops the rest."""
    from apps.messaging import outreach

    results: list[dict] = []
    pause = float(getattr(settings, "INVITATION_EMAIL_PAUSE_SECONDS", 1.0))
    pool = outreach.kii_introduction_candidates(options.get("groups") or GROUPS, named_only=bool(options.get("named_only")))
    for record in [r for r in pool if not outreach.tried_this_number(r)][: batch.requested * 2]:
        if batch.sent + batch.failed >= batch.requested:
            break
        try:
            sent = outreach.send_kii_introduction(record, user=batch.created_by)
            batch.sent += 1
            results.append({"kii_id": record.kii_id, "outcome": "sent", "detail": f"{sent.channel} {sent.number_masked}"})
        except outreach.OutreachError as exc:
            if exc.code == "daily_limit_reached":
                batch.skipped += 1
                results.append({"kii_id": record.kii_id, "outcome": "skipped", "detail": str(exc)[:200]})
                break
            failed = exc.code in ("twilio_refused",)
            batch.failed += failed
            batch.skipped += not failed
            results.append({"kii_id": record.kii_id, "outcome": "failed" if failed else "skipped", "detail": str(exc)[:300]})
        batch.results = results
        batch.save(update_fields=["sent", "failed", "skipped", "results"])
        if pause:
            time.sleep(pause)
    return results


def send_one(record, *, user, link_base: str, channels=("EMAIL",)) -> dict:
    """Issue one link and send it on every chosen channel the record can receive, as one step: if none gets through,
    the link and the move to INVITED are undone."""
    with transaction.atomic():
        reachable = reachable_channels(record, channels)
        if not reachable:
            raise KIIInvitationSendError("no_contact", "no contact on file for the chosen channels")
        raw_token, raw_code, token = issue_kii_invitation(record, channel=reachable[0], issued_by=user)
        link = f"{link_base}/ki/{raw_token}"
        sent, problems = [], []
        for channel in reachable:
            try:
                if channel == "EMAIL":
                    result = email_kii_invitation(token, link=link, manual_code=raw_code, user=user)
                else:
                    result = text_kii_invitation(token, channel=channel, link=link, manual_code=raw_code, user=user)
                sent.append(f"{main.CHANNEL_LABEL[channel]} {result['sent_to']}")
            except KIIInvitationSendError as exc:
                problems.append(f"{main.CHANNEL_LABEL[channel]}: {exc}")
            except Exception as exc:  # the mail server refused or timed out
                problems.append(f"{main.CHANNEL_LABEL[channel]} could not be sent ({type(exc).__name__})")
        if not sent:
            raise NothingSent("; ".join(problems))
        return {"sent_to": "; ".join(sent), "problems": problems}


def run_batch(batch) -> None:
    """Sends a KII batch (from the Celery task, through apps.invitations.batch.run_batch). One record failing never
    stops the rest; never raises."""
    user, link_base = batch.created_by, portal_base(None)
    options = batch.options or {}
    pause = float(getattr(settings, "INVITATION_EMAIL_PAUSE_SECONDS", 1.0))
    chosen = list(batch.channels or ["EMAIL"])
    results: list[dict] = []
    try:
        if options.get("intro"):
            results = _run_intro_batch(batch, options)
        pool = [] if options.get("intro") else list(candidates(chosen, options.get("groups") or GROUPS, named_only=bool(options.get("named_only")))[: batch.requested * 2])
        for record in pool:
            if batch.sent + batch.failed >= batch.requested:
                break
            channels = [channel for channel in chosen if main.channel_left_today(channel) > 0]
            if not channels:
                results.append({"kii_id": record.kii_id, "outcome": "skipped", "detail": "today's sending limits reached"})
                batch.skipped += 1
                break
            record.refresh_from_db()
            if record.status != KIIStatus.PROSPECT:  # invited from the record page since the batch started
                results.append({"kii_id": record.kii_id, "outcome": "skipped", "detail": "already invited"})
                batch.skipped += 1
                continue
            try:
                sent = send_one(record, user=user, link_base=link_base, channels=channels)
                batch.sent += 1
                detail = sent["sent_to"] + (f" (not sent: {'; '.join(sent['problems'])})" if sent["problems"] else "")
                results.append({"kii_id": record.kii_id, "outcome": "sent", "detail": detail[:300]})
            except KIIInvitationSendError as exc:
                batch.skipped += 1
                results.append({"kii_id": record.kii_id, "outcome": "skipped", "detail": str(exc)[:200]})
            except Exception as exc:  # no channel got through: nothing was kept for this record
                logger.warning("KII batch %s: invitation to %s failed: %s", batch.pk, record.kii_id, exc)
                batch.failed += 1
                reason = str(exc) if isinstance(exc, NothingSent) else f"could not be sent ({type(exc).__name__})"
                results.append({"kii_id": record.kii_id, "outcome": "failed", "detail": reason[:300]})
            batch.results = results
            batch.save(update_fields=["sent", "failed", "skipped", "results"])  # the screen shows progress
            if pause:
                time.sleep(pause)
        batch.status = InvitationBatchStatus.DONE
    except Exception:
        logger.exception("KII invitation batch %s crashed", batch.pk)
        batch.status, batch.error = InvitationBatchStatus.FAILED, "The batch stopped unexpectedly. Records already sent stay sent."
    finally:
        batch.results, batch.finished_at = results, timezone.now()
        batch.save()
        log_action("kii_invitations.batch_completed", batch, {
            "sent": batch.sent, "failed": batch.failed, "skipped": batch.skipped,
            "failed_records": [r["kii_id"] for r in results if r["outcome"] == "failed"],
            "user_id": getattr(user, "id", None),
        }, user=user)
