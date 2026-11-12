"""Who phones the people who are sent a link (PI instruction, 12 Nov 2026).

One Research Assistant (calls) now does all the calling. So that nobody who is given a link is left on no call list,
every newly issued link -- a YES to the introduction, a link sent by hand, a batch -- puts its Main-400 case or KII
record on the list of the account named in settings.RA_NEW_LINK_ASSIGNEE. Empty (the default) switches this off.

It is called from issue_invitation() and issue_kii_invitation(), the two places every link is issued, so no route
can forget it. It never changes who may be invited: is_invitable() has already passed by then (AGENTS.md rule 4).

Left as they are:
- work already on an active Research Assistant (calls) account;
- a case or record marked as a duplicate: the PI keeps those off the call lists on purpose.
"""

import logging

from django.conf import settings

from apps.audit.utils import log_action

from .roles import TELEPHONE_RA

logger = logging.getLogger(__name__)


def new_link_assignee():
    """The active Research Assistant (calls) account named in RA_NEW_LINK_ASSIGNEE, or None."""
    from apps.accounts.models import User

    username = (getattr(settings, "RA_NEW_LINK_ASSIGNEE", "") or "").strip()
    if not username:
        return None
    user = User.objects.filter(username=username, is_active=True, role__name=TELEPHONE_RA).first()
    if user is None:
        logger.warning("RA_NEW_LINK_ASSIGNEE=%s is not an active Research Assistant (calls) account; nothing assigned.", username)
    return user


def assign_on_link(subject, *, issued_by=None) -> bool:
    """Put the Main-400 case or KII record whose link was just issued on the named RA's call list. True if it moved."""
    if "duplicate_of" in (subject.metadata or {}):
        return False
    current = subject.assigned_ra
    if current is not None and current.is_active and getattr(current.role, "name", "") == TELEPHONE_RA:
        return False
    ra = new_link_assignee()
    if ra is None:
        return False
    subject.assigned_ra = ra
    subject.save(update_fields=["assigned_ra", "updated_at"])
    kii = hasattr(subject, "kii_id")
    ident = {"study": "KII", "kii_ids": [subject.kii_id]} if kii else {"study": "QUAN", "sample_ids": [subject.sample_id]}
    log_action("ra.assigned", subject, {**ident, "to": ra.username, "from": current.username if current else "unassigned",
                                        "reason": "A link was issued: everyone given a link goes on this research assistant's call list"},
               user=issued_by)
    return True
