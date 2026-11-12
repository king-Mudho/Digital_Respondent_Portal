"""Is there any record that a link reached the person? (12 Nov 2026)

Issuing an invitation and sending it are two steps: the link is shown once, and a person then sends it -- from the
portal (Twilio, the study email) or by hand (their own WhatsApp, email app or SMS). Issuing also switches off the
link the respondent already has. So a second "issue" with no send leaves the portal showing a working link nobody
holds: SID-2026-000385 said YES on 14 Oct and was sent a link; two more were issued on 19 Oct and never sent; the
nightly renewal kept the last one alive; and on 12 Nov a reminder told them to "use the link you were sent", which
answered "The link is no longer available". Nothing on any screen showed it, and a by-hand send left no trace at
all, so a link sent by hand looked the same as one never sent.

on_record() says which links have evidence of having been sent, and record_by_hand() is what the send panel's
by-hand buttons now write. Calls shows the rest as "no record this link was sent".
"""

from apps.audit.utils import log_action

BY_HAND_CHANNELS = ("WHATSAPP", "SMS", "EMAIL")
SENT_ACTIONS = {
    False: ["invitation.emailed", "invitation.sms_sent", "invitation.whatsapp_sent", "invitation.sent_by_hand"],
    True: ["kii_invitation.emailed", "kii_invitation.sms_sent", "kii_invitation.whatsapp_sent", "kii_invitation.sent_by_hand"],
}
# A link the respondent has opened reached them, however it was sent.
UNOPENED = ("GENERATED", "SENT")


def on_record(tokens, *, kii: bool = False) -> set[int]:
    """The ids of those `tokens` (InvitationToken, or KIIInvitationToken with kii=True) with evidence that the link
    reached the person: a portal message that was not refused or undelivered, an email / SMS / WhatsApp send or a
    by-hand send in the audit log, or the respondent having opened it."""
    from apps.audit.models import AuditEvent
    from apps.messaging.models import ProviderMessage, ProviderStatus

    tokens = list(tokens)
    found = {t.pk for t in tokens if t.first_opened_at is not None or t.status not in UNOPENED}
    rest = [t.pk for t in tokens if t.pk not in found]
    if not rest:
        return found
    field = "kii_invitation_token_id" if kii else "invitation_token_id"
    found |= set(ProviderMessage.objects.filter(**{f"{field}__in": rest})
                 .exclude(status__in=[ProviderStatus.FAILED, ProviderStatus.UNDELIVERED]).values_list(field, flat=True))
    logged = AuditEvent.objects.filter(object_type="KIIInvitationToken" if kii else "InvitationToken",
                                       object_id__in=[str(pk) for pk in rest], action__in=SENT_ACTIONS[kii])
    found |= {int(pk) for pk in logged.values_list("object_id", flat=True)}
    return found


def record_by_hand(token, *, channel: str, user) -> None:
    """A person pressed one of the panel's by-hand send buttons for this link (their own WhatsApp, SMS or email app).
    The portal cannot see whether the message was then sent; this records that they went to send it, and by whom."""
    kii = hasattr(token, "kii_record_id")
    ident = {"kii_id": token.kii_record.kii_id} if kii else {"sample_id": token.sample_case.sample_id}
    log_action("kii_invitation.sent_by_hand" if kii else "invitation.sent_by_hand", token,
               {**ident, "channel": channel, "user_id": getattr(user, "id", None)}, user=user)
