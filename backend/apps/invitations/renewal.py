"""Keep the links of people on a Research Assistant's call list working (PI request, 8 Nov 2026).

On the day the two Research Assistants (calls) were given the open Main-400 and KII work, 198 of the 205 live Main-400
links and all 130 live KII links had passed their 14-day date, so nearly every call would have opened on "This link has
expired". Issuing new links would have made every message already sent stop working and meant sending all of them
again. Renewing moves the date of the link the person already has, so the WhatsApp or email they were sent works again
and nothing is sent.

A link is renewed only when all of these hold, checked here for every caller (the nightly task, the management command):

- it is still open: not submitted, QA-passed, revoked, or superseded by a newer invitation (EXPIRED status);
- it belongs to a Main-400 case at S05-S07 or an activated Reserve (never a LOCKED Reserve: is_invitable(), AGENTS.md
  rule 4), or a KII record still at INVITED;
- nothing on the case is submitted, it is not marked a duplicate, and the latest participation consent is not declined
  or withdrawn (withdrawing revokes the links anyway);
- the case or record is assigned to a Research Assistant (calls). The PI's held duplicates and identity checks were
  deliberately kept off those lists, so this also keeps their links as they are.

How close to its date a link must be, and the new date (INVITATION_TOKEN_EXPIRY_DAYS from now), are settings
(AGENTS.md rule 7), and INVITATION_AUTO_RENEW switches the nightly run off. Every renewed link gets an audit entry
with its old and new dates."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.utils import log_action
from apps.consent.models import ConsentDecision, ConsentType
from apps.consent.services import latest_consent
from apps.invitations.models import InvitationToken, TokenStatus
from apps.kii.models import KIIInvitationToken, KIIInvitationTokenStatus, KIIStatus
from apps.ra.roles import TELEPHONE_RA
from apps.sampling.models import ReserveStatus, SampleType, WorkflowStatus
from apps.sampling.services import is_invitable

OPEN_MAIN = [TokenStatus.GENERATED, TokenStatus.SENT, TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED,
             TokenStatus.CONSENTED, TokenStatus.SURVEY_STARTED]
FINISHED_MAIN = [TokenStatus.SUBMITTED, TokenStatus.QA_PASSED]
OPEN_KII = [KIIInvitationTokenStatus.GENERATED, KIIInvitationTokenStatus.SENT, KIIInvitationTokenStatus.OPENED,
            KIIInvitationTokenStatus.CONSENTED, KIIInvitationTokenStatus.STARTED]
STILL_WAITING = [WorkflowStatus.S05_INVITATION_SENT, WorkflowStatus.S06_INVITATION_OPENED, WorkflowStatus.S07_SURVEY_STARTED]
REFUSED = (ConsentDecision.DECLINED, ConsentDecision.WITHDRAWN)


def _main_candidates(cutoff):
    return (InvitationToken.objects.filter(status__in=OPEN_MAIN, expires_at__lte=cutoff,
                                           sample_case__assigned_ra__role__name=TELEPHONE_RA)
            .filter(Q(sample_case__sample_type=SampleType.MAIN, sample_case__workflow_status__in=STILL_WAITING)
                    | Q(sample_case__sample_type=SampleType.RESERVE, sample_case__status=ReserveStatus.ACTIVATED))
            .exclude(sample_case__metadata__has_key="duplicate_of")
            .exclude(sample_case__invitation_tokens__status__in=FINISHED_MAIN)
            .select_related("sample_case").distinct().order_by("sample_case__sample_id", "pk"))


def _kii_candidates(cutoff):
    return (KIIInvitationToken.objects.filter(status__in=OPEN_KII, expires_at__lte=cutoff,
                                              kii_record__status=KIIStatus.INVITED,
                                              kii_record__assigned_ra__role__name=TELEPHONE_RA)
            .exclude(kii_record__metadata__has_key="duplicate_of")
            .select_related("kii_record").order_by("kii_record__kii_id", "pk"))


def _refused(subject) -> bool:
    consent = latest_consent(subject, ConsentType.PARTICIPATION)
    return consent is not None and consent.decision in REFUSED


def renew_call_list_links(*, apply: bool = False, within_days: float | None = None, user=None) -> dict:
    """Renew every link on a Research Assistant's list that has expired or will within `within_days`
    (INVITATION_RENEW_WITHIN_DAYS). Dry run unless `apply`. Returns what was (or would be) renewed and what was left."""
    now = timezone.now()
    if within_days is None:
        within_days = getattr(settings, "INVITATION_RENEW_WITHIN_DAYS", 2)
    cutoff = now + timedelta(days=within_days)
    new_expiry = now + timedelta(days=getattr(settings, "INVITATION_TOKEN_EXPIRY_DAYS", 14))
    renewed, skipped = [], []

    for token in _main_candidates(cutoff):
        case = token.sample_case
        entry = {"kind": "main", "id": case.sample_id, "token_id": token.pk, "channel": token.channel,
                 "was": token.expires_at, "expired": token.expires_at <= now}
        if not is_invitable(case) or _refused(case):
            skipped.append({**entry, "why": "not invitable" if not is_invitable(case) else "declined or withdrew"})
            continue
        renewed.append(entry)
        if apply:
            with transaction.atomic():
                InvitationToken.objects.filter(pk=token.pk, status__in=OPEN_MAIN).update(expires_at=new_expiry)
                log_action("invitation.renewed", token, {
                    "sample_id": case.sample_id, "channel": token.channel, "previous_expiry": token.expires_at.isoformat(),
                    "new_expiry": new_expiry.isoformat(), "reason": "on a Research Assistant's call list"}, user=user)

    for token in _kii_candidates(cutoff):
        record = token.kii_record
        entry = {"kind": "kii", "id": record.kii_id, "token_id": token.pk, "channel": token.channel,
                 "was": token.expires_at, "expired": token.expires_at <= now}
        if _refused(record):
            skipped.append({**entry, "why": "declined or withdrew"})
            continue
        renewed.append(entry)
        if apply:
            with transaction.atomic():
                KIIInvitationToken.objects.filter(pk=token.pk, status__in=OPEN_KII).update(expires_at=new_expiry)
                log_action("kii_invitation.renewed", token, {
                    "kii_id": record.kii_id, "channel": token.channel, "previous_expiry": token.expires_at.isoformat(),
                    "new_expiry": new_expiry.isoformat(), "reason": "on a Research Assistant's call list"}, user=user)

    return {"renewed": renewed, "skipped": skipped, "new_expiry": new_expiry, "applied": apply}
