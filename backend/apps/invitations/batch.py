"""Batch email invitations, started by the PI or Field Coordinator.

There is no separate sending path: each case goes through issue_invitation() (which checks is_invitable(), AGENTS.md
rule 4, and moves S03/S04 to S05) and email_invitation() (the approved wording and the invitation.emailed audit entry),
exactly as the case-page Email button does. Only verified cases are invited (S03 or S04, PI decision 2026-10-03),
with a respondent email and no open invitation.

Each case is issued and emailed as ONE database transaction: if the email fails, the new link and the status change
are undone together, so a case never shows "Invitation sent" for an email that never left. The batch records what
happened case by case, with masked addresses only. Caps are settings (AGENTS.md rule 7).
"""

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.audit.utils import log_action

from .messages import InvitationSendError, _mask, email_invitation, portal_base, recipients
from .models import Channel, InvitationBatch, InvitationBatchStatus, InvitationToken, TokenStatus
from .services import TokenNotInvitable, issue_invitation

logger = logging.getLogger(__name__)

VERIFIED = ["S03", "S04"]
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


def batch_candidates():
    """Verified cases that may be invited, with a respondent email and no open invitation."""
    from apps.contacts.models import Respondent
    from apps.sampling.models import ReserveStatus, SampleCase, SampleType

    has_email = Respondent.objects.filter(sample_case=OuterRef("pk")).exclude(email="")
    open_invitation = InvitationToken.objects.filter(
        sample_case=OuterRef("pk"), status__in=OPEN_STATUSES, expires_at__gt=timezone.now(),
    )
    return (
        SampleCase.objects.filter(Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED))
        .filter(workflow_status__in=VERIFIED)
        .filter(Exists(has_email)).exclude(Exists(open_invitation))
        .select_related("organisation").order_by("sample_id")
    )


def preview(limit: int = 10) -> list[dict]:
    from apps.sampling.services import is_invitable

    rows = []
    for case in batch_candidates()[:limit]:
        if is_invitable(case):
            rows.append({
                "sample_id": case.sample_id, "organisation": case.organisation.name if case.organisation else "",
                "email": _mask(recipients(case)["email_to"]),
            })
    return rows


def start_batch(limit: int, *, user) -> InvitationBatch:
    from apps.kobo.submission_copies import email_is_configured

    if not email_is_configured():
        raise BatchError("email_not_configured", "Email isn't set up on the server yet. Run deploy/configure-email.sh first.", 503)
    allowed = min(per_batch_max(), left_today())
    if allowed < 1:
        raise BatchError("daily_limit_reached", f"Today's limit of {daily_max()} emailed invitations has been reached. Try again tomorrow.", 409)
    if not 1 <= limit <= allowed:
        raise BatchError("bad_limit", f"Choose between 1 and {allowed} invitations.")
    if InvitationBatch.objects.filter(status=InvitationBatchStatus.RUNNING, started_at__gte=timezone.now() - timedelta(hours=1)).exists():
        raise BatchError("already_running", "A batch is already sending. Wait for it to finish.", 409)
    batch = InvitationBatch.objects.create(created_by=user, requested=limit)
    log_action("invitations.batch_started", batch, {"requested": limit, "user_id": getattr(user, "id", None)}, user=user)
    return batch


def send_one(case, *, user, link_base: str) -> dict:
    """Issue and email one invitation as one all-or-nothing step."""
    with transaction.atomic():
        raw_token, raw_code, token = issue_invitation(case, channel=Channel.EMAIL, issued_by=user)
        return email_invitation(token, link=f"{link_base}/i/{raw_token}", manual_code=raw_code, user=user)


def run_batch(batch_id: int) -> None:
    """Sends the batch (from the Celery task). One case failing never stops the rest; never raises."""
    from apps.sampling.services import is_invitable

    batch = InvitationBatch.objects.select_related("created_by").get(pk=batch_id)
    user, link_base = batch.created_by, portal_base(None)
    pause = float(getattr(settings, "INVITATION_EMAIL_PAUSE_SECONDS", 1.0))
    results: list[dict] = []
    try:
        for case in list(batch_candidates()[: batch.requested * 2]):
            if batch.sent + batch.failed >= batch.requested:
                break
            if left_today() < 1:
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": "today's email limit reached"})
                batch.skipped += 1
                break
            if not is_invitable(case):
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": "not invitable"})
                batch.skipped += 1
                continue
            try:
                sent = send_one(case, user=user, link_base=link_base)
                batch.sent += 1
                results.append({"sample_id": case.sample_id, "outcome": "sent", "detail": sent["sent_to"]})
            except (TokenNotInvitable, InvitationSendError) as exc:
                batch.skipped += 1
                results.append({"sample_id": case.sample_id, "outcome": "skipped", "detail": str(exc)[:200]})
            except Exception as exc:  # the mail server refused or timed out: nothing was kept for this case
                logger.warning("Batch %s: email to %s failed: %s", batch.pk, case.sample_id, exc)
                batch.failed += 1
                results.append({"sample_id": case.sample_id, "outcome": "failed", "detail": f"email could not be sent ({type(exc).__name__})"})
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
