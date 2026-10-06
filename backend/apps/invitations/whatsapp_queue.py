"""WhatsApp send queue: invitations ready to send by WhatsApp, one tap each (PI decision 2026-10-03).

The study has no WhatsApp Business Platform account, so nothing is sent automatically. This lists the verified cases
(S03 or S04) that have a WhatsApp or phone number and no open invitation; preparing one issues the invitation through
issue_invitation() (is_invitable(), AGENTS.md rule 4; the move to S05; the invitation.issued audit entry) and returns a
wa.me link with the approved WhatsApp message, which the RA opens and sends from their own phone. A Contact RA sees
and prepares only the cases assigned to them.
"""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .batch import OPEN_STATUSES, VERIFIED
from .messages import build_messages, portal_base, recipients
from .models import Channel, InvitationToken
from .services import issue_invitation


class QueueError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def _is_contact_ra(user) -> bool:
    return getattr(getattr(user, "role", None), "name", None) == "CONTACT_RA"


def queue_cases(user):
    from apps.contacts.models import Respondent
    from apps.sampling.models import ReserveStatus, SampleCase, SampleType

    has_number = Respondent.objects.filter(sample_case=OuterRef("pk")).filter(~Q(whatsapp_number="") | ~Q(phone=""))
    open_invitation = InvitationToken.objects.filter(
        sample_case=OuterRef("pk"), status__in=OPEN_STATUSES, expires_at__gt=timezone.now(),
    )
    cases = (
        SampleCase.objects.filter(Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED))
        .filter(workflow_status__in=VERIFIED)
        .filter(Exists(has_number)).exclude(Exists(open_invitation))
        .select_related("organisation").prefetch_related("respondents").order_by("sample_id")
    )
    return cases.filter(assigned_ra=user) if _is_contact_ra(user) else cases


def _masked(digits: str) -> str:
    return f"+{digits[:3]} ••• {digits[-3:]}" if len(digits) > 6 else "•••"


def queue_rows(user, limit: int = 50) -> list[dict]:
    from apps.sampling.services import is_invitable

    rows = []
    for case in queue_cases(user)[:limit]:
        who = recipients(case)
        if is_invitable(case) and who["whatsapp_to"]:
            rows.append({
                "sample_id": case.sample_id, "organisation": case.organisation.name if case.organisation else "",
                "to_name": who["whatsapp_to_name"], "number": _masked(who["whatsapp_to"]),
            })
    return rows


def prepare(sample_id: str, *, user, link_base: str | None) -> dict:
    """Issues the invitation for one queued case and returns the WhatsApp link to send it with.

    Also returns the link and code (shown once, like the case page) and where an email would go, so the RA can email
    the same invitation from the queue. Until 2026-10-06 only the WhatsApp text came back: emailing an organisation
    that also had an address meant issuing a second invitation on the case page, which made the WhatsApp link stop
    working -- 49 organisations were left holding a dead WhatsApp link that way."""
    from apps.kobo.submission_copies import email_is_configured
    from apps.messaging.services import whatsapp_link

    from .messages import _mask

    case = queue_cases(user).filter(sample_id=sample_id).first()
    if case is None:
        raise QueueError("not_in_queue", "This case is not waiting for a WhatsApp invitation (it may already have one).", 409)
    who = recipients(case)
    if not who["whatsapp_to"]:
        raise QueueError("no_number", "No WhatsApp or phone number is recorded for this case.", 409)
    raw_token, raw_code, token = issue_invitation(case, channel=Channel.WHATSAPP, issued_by=user)
    link = f"{portal_base(link_base)}/i/{raw_token}"
    text = build_messages(sample_case=case, link=link, manual_code=raw_code, expires_at=token.expires_at,
                          to_name=who["whatsapp_to_name"])["whatsapp"]
    return {"sample_id": case.sample_id, "token_id": token.id, "expires_at": token.expires_at,
            "whatsapp_url": whatsapp_link(who["whatsapp_to"], text), "message": text,
            "link": link, "manual_code": raw_code,
            "email_to": _mask(who["email_to"]) if who["email_to"] else "", "email_configured": email_is_configured()}
