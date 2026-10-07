"""Batch invitations, started by the PI or Field Coordinator: by email, and by SMS and WhatsApp through Twilio
(channels added 2026-10-07).

There is no separate sending path: each case goes through issue_invitation() (which checks is_invitable(), AGENTS.md
rule 4, and moves S03/S04 to S05), then email_invitation() and text_invitation() -- the approved wording and audit
entries -- exactly as the case-page buttons do. Only verified cases are invited (S03 or S04, PI decision 2026-10-03),
with a contact for at least one chosen channel and no open invitation.

One invitation per case, sent on every chosen channel the case can receive, so the WhatsApp message and the email
carry the same working link. The case is issued and sent as ONE database transaction: if no channel gets through,
the new link and the status change are undone together, so a case never shows "Invitation sent" for a message that
never left. The batch records what happened case by case, with masked addresses and numbers only. Caps are settings
(AGENTS.md rule 7).
"""

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.audit.utils import log_action

from .messages import (
    InvitationSendError,
    _mask,
    build_messages,
    email_invitation,
    portal_base,
    recipients,
    text_invitation,
)
from .models import InvitationBatch, InvitationBatchStatus, InvitationToken, TokenStatus
from .services import TokenNotInvitable, issue_invitation

logger = logging.getLogger(__name__)

VERIFIED = ["S03", "S04"]
CHANNELS = ("EMAIL", "SMS", "WHATSAPP")
CHANNEL_LABEL = {"EMAIL": "email", "SMS": "SMS", "WHATSAPP": "WhatsApp"}
RECIPIENT_FIELD = {"EMAIL": "email_to", "SMS": "sms_to", "WHATSAPP": "whatsapp_to"}
OPEN_STATUSES = [
    TokenStatus.GENERATED, TokenStatus.SENT, TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED,
    TokenStatus.CONSENTED, TokenStatus.SURVEY_STARTED,
]


class BatchError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def per_batch_max() -> int:
    return max(1, int(getattr(settings, "INVITATION_EMAIL_BATCH_MAX", 100)))


def daily_max() -> int:
    return max(1, int(getattr(settings, "INVITATION_EMAIL_DAILY_MAX", 300)))


def emailed_today() -> int:
    from apps.audit.models import AuditEvent

    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return AuditEvent.objects.filter(action="invitation.emailed", created_at__gte=start).count()


def left_today() -> int:
    return max(0, daily_max() - emailed_today())


def batch_candidates(channels=("EMAIL",)):
    """Verified cases that may be invited, with a contact for at least one of `channels` and no open invitation.
    Whether a phone number is a mobile is decided per case by recipients(), so SMS/WhatsApp candidates are those with
    any number on file."""
    from apps.contacts.models import Respondent
    from apps.sampling.models import ReserveStatus, SampleCase, SampleType

    people = Respondent.objects.filter(sample_case=OuterRef("pk"))
    reachable = Q(pk__in=[])
    if "EMAIL" in channels:
        reachable |= Q(Exists(people.exclude(email="")))
    if "SMS" in channels or "WHATSAPP" in channels:
        reachable |= Q(Exists(people.filter(~Q(phone="") | ~Q(whatsapp_number=""))))
    open_invitation = InvitationToken.objects.filter(
        sample_case=OuterRef("pk"), status__in=OPEN_STATUSES, expires_at__gt=timezone.now(),
    )
    return (
        SampleCase.objects.filter(Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED))
        .filter(workflow_status__in=VERIFIED)
        .filter(reachable).exclude(Exists(open_invitation))
        .select_related("organisation").prefetch_related("respondents").order_by("sample_id")
    )


def reachable_channels(case, channels) -> list[str]:
    """The chosen channels this case can actually receive: an email address, a mobile for SMS and WhatsApp."""
    who = recipients(case)
    return [channel for channel in channels if who[RECIPIENT_FIELD[channel]]]


def channel_configured(channel: str) -> bool:
    from apps.kobo.submission_copies import email_is_configured
    from apps.messaging import twilio_client as tw

    return {"EMAIL": email_is_configured, "SMS": tw.sms_configured, "WHATSAPP": tw.whatsapp_configured}[channel]()


def channel_left_today(channel: str) -> int:
    from apps.messaging import outbound

    return left_today() if channel == "EMAIL" else outbound.left_today(channel)


def channel_daily_max(channel: str) -> int:
    from apps.messaging import outbound

    return daily_max() if channel == "EMAIL" else outbound.daily_max(channel)


def sms_cost_usd(cases) -> float:
    """What the invitation SMS to these cases would cost: each message's segments at Twilio's Zimbabwe price, with a
    link of a real link's length (a token_urlsafe(32) is 43 characters)."""
    from apps.messaging import twilio_client as tw

    link = f"{portal_base(None)}/i/{'x' * 43}"
    expires = timezone.now() + timedelta(days=getattr(settings, "INVITATION_TOKEN_EXPIRY_DAYS", 14))
    segments = sum(
        tw.sms_segments(tw.with_opt_out(build_messages(sample_case=case, link=link, manual_code="ABCD2345", expires_at=expires)["sms"]))
        for case in cases
    )
    return round(segments * float(settings.TWILIO_SMS_SEGMENT_PRICE_USD), 2)


def channel_summary() -> dict:
    """Per channel: set up or not, how many verified cases could receive it, and what is left of today's cap."""
    from apps.sampling.services import is_invitable

    cases = [case for case in batch_candidates(CHANNELS) if is_invitable(case)]
    by_channel = {channel: [] for channel in CHANNELS}
    for case in cases:
        for channel in reachable_channels(case, CHANNELS):
            by_channel[channel].append(case)
    return {
        channel: {
            "configured": channel_configured(channel), "ready": len(by_channel[channel]),
            "left_today": channel_left_today(channel), "daily_max": channel_daily_max(channel),
            **({"cost_usd_all": sms_cost_usd(by_channel[channel])} if channel == "SMS" else {}),
        }
        for channel in CHANNELS
    }


def preview(limit: int = 10, channels=("EMAIL",)) -> list[dict]:
    from apps.messaging import twilio_client as tw
    from apps.sampling.services import is_invitable

    rows = []
    for case in batch_candidates(channels)[:limit]:
        if is_invitable(case):
            who = recipients(case)
            mobile = who["sms_to"] or who["whatsapp_to"]
            rows.append({
                "sample_id": case.sample_id, "organisation": case.organisation.name if case.organisation else "",
                "email": _mask(who["email_to"]) if who["email_to"] else "",
                "mobile": tw.mask(mobile) if mobile else "",
                "channels": reachable_channels(case, channels),
            })
    return rows


def clean_channels(channels) -> list[str]:
    chosen = [channel for channel in CHANNELS if channel in (channels or [])]
    if not chosen:
        raise BatchError("no_channel", "Choose at least one way to send: email, SMS or WhatsApp.")
    return chosen


def start_batch(limit: int, *, user, channels=("EMAIL",)) -> InvitationBatch:
    channels = clean_channels(channels)
    for channel in channels:
        if not channel_configured(channel):
            how = "deploy/configure-email.sh" if channel == "EMAIL" else "deploy/configure-twilio.sh"
            label = CHANNEL_LABEL[channel][:1].upper() + CHANNEL_LABEL[channel][1:]
            raise BatchError(f"{channel.lower()}_not_configured", f"{label} isn't set up on the server yet. Run {how} first.", 503)
    allowed = min([per_batch_max()] + [channel_left_today(channel) for channel in channels])
    if allowed < 1:
        raise BatchError("daily_limit_reached", "Today's sending limit has been reached for a chosen channel. Try again tomorrow.", 409)
    if not 1 <= limit <= allowed:
        raise BatchError("bad_limit", f"Choose between 1 and {allowed} invitations.")
    if InvitationBatch.objects.filter(status=InvitationBatchStatus.RUNNING, started_at__gte=timezone.now() - timedelta(hours=1)).exists():
        raise BatchError("already_running", "A batch is already sending. Wait for it to finish.", 409)
    batch = InvitationBatch.objects.create(created_by=user, requested=limit, channels=channels)
    log_action("invitations.batch_started", batch, {"requested": limit, "channels": channels,
                                                    "user_id": getattr(user, "id", None)}, user=user)
    return batch


class NothingSent(Exception):
    """No chosen channel got through for a case; raised inside its transaction so the invitation is undone."""


def send_one(case, *, user, link_base: str, channels=("EMAIL",)) -> dict:
    """Issue one invitation and send it on every chosen channel the case can receive, as one step: if none gets
    through, the invitation and the move to S05 are undone."""
    with transaction.atomic():
        reachable = reachable_channels(case, channels)
        if not reachable:
            raise InvitationSendError("no_contact", "no contact on file for the chosen channels")
        raw_token, raw_code, token = issue_invitation(case, channel=reachable[0], issued_by=user)
        link = f"{link_base}/i/{raw_token}"
        sent, problems = [], []
        for channel in reachable:
            try:
                if channel == "EMAIL":
                    result = email_invitation(token, link=link, manual_code=raw_code, user=user)
                else:
                    result = text_invitation(token, channel=channel, link=link, manual_code=raw_code, user=user)
                sent.append(f"{CHANNEL_LABEL[channel]} {result['sent_to']}")
            except InvitationSendError as exc:
                problems.append(f"{CHANNEL_LABEL[channel]}: {exc}")
            except Exception as exc:  # the mail server refused or timed out
                problems.append(f"{CHANNEL_LABEL[channel]} could not be sent ({type(exc).__name__})")
        if not sent:
            raise NothingSent("; ".join(problems))
        return {"sent_to": "; ".join(sent), "problems": problems}


def run_batch(batch_id: int) -> None:
    """Sends the batch (from the Celery task). One case failing never stops the rest; never raises."""
    from apps.sampling.services import is_invitable

    batch = InvitationBatch.objects.select_related("created_by").get(pk=batch_id)
    user, link_base = batch.created_by, portal_base(None)
    pause = float(getattr(settings, "INVITATION_EMAIL_PAUSE_SECONDS", 1.0))
    chosen = list(batch.channels or ["EMAIL"])
    results: list[dict] = []
    try:
        for case in list(batch_candidates(chosen)[: batch.requested * 2]):
            if batch.sent + batch.failed >= batch.requested:
                break
            channels = [channel for channel in chosen if channel_left_today(channel) > 0]
            if not channels:
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": "today's sending limits reached"})
                batch.skipped += 1
                break
            if not is_invitable(case):
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": "not invitable"})
                batch.skipped += 1
                continue
            try:
                sent = send_one(case, user=user, link_base=link_base, channels=channels)
                batch.sent += 1
                detail = sent["sent_to"] + (f" (not sent: {'; '.join(sent['problems'])})" if sent["problems"] else "")
                results.append({"sample_id": case.sample_id, "outcome": "sent", "detail": detail[:300]})
            except (TokenNotInvitable, InvitationSendError) as exc:
                batch.skipped += 1
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": str(exc)[:200]})
            except Exception as exc:  # no channel got through: nothing was kept for this case
                logger.warning("Batch %s: invitation to %s failed: %s", batch.pk, case.sample_id, exc)
                batch.failed += 1
                reason = str(exc) if isinstance(exc, NothingSent) else f"email could not be sent ({type(exc).__name__})"
                results.append({"sample_id": case.sample_id, "outcome": "failed", "detail": reason[:300]})
            batch.results = results
            batch.save(update_fields=["sent", "failed", "skipped", "results"])  # the screen shows progress
            if pause:
                time.sleep(pause)
        batch.status = InvitationBatchStatus.DONE
    except Exception:
        logger.exception("Invitation batch %s crashed", batch.pk)
        batch.status, batch.error = InvitationBatchStatus.FAILED, "The batch stopped unexpectedly. Cases already sent stay sent."
    finally:
        batch.results, batch.finished_at = results, timezone.now()
        batch.save()
        log_action("invitations.batch_completed", batch, {
            "sent": batch.sent, "failed": batch.failed, "skipped": batch.skipped,
            "failed_cases": [r["sample_id"] for r in results if r["outcome"] == "failed"],
            "user_id": getattr(user, "id", None),
        }, user=user)
