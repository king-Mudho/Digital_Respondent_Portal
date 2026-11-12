"""Who phones the people who are sent a link (PI instruction, 12 Nov 2026).

So that nobody who is given a link is left on no call list, every newly issued link -- a YES to the introduction, a
link sent by hand, a batch -- puts its Main-400 case or KII record on the list of a Research Assistant (calls) named
in settings.RA_NEW_LINK_ASSIGNEE. Empty (the default) switches this off.

The setting holds one username, or several separated by commas. With several, the link goes to whichever of them has
the least open work of that kind (open Main-400 cases, or open KII records), the first named winning a tie: so new
links alternate between RAs whose lists are level, and a shorter list catches up first. It began the same morning as
one name, when one RA did all the calling; the second RA came back that afternoon and the PI asked for the links to
be shared.

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


def new_link_assignees() -> list:
    """The active Research Assistant (calls) accounts named in RA_NEW_LINK_ASSIGNEE, in the order they are named."""
    from apps.accounts.models import User

    names = [n.strip() for n in (getattr(settings, "RA_NEW_LINK_ASSIGNEE", "") or "").split(",") if n.strip()]
    if not names:
        return []
    found = {u.username: u for u in User.objects.filter(username__in=names, is_active=True, role__name=TELEPHONE_RA)}
    missing = [n for n in names if n not in found]
    if missing:
        logger.warning("RA_NEW_LINK_ASSIGNEE names %s, not an active Research Assistant (calls) account; skipped.", ", ".join(missing))
    return [found[n] for n in names if n in found]


def _open_work(user, *, kii: bool) -> int:
    if kii:
        from apps.kii.models import KIIRecord, KIIStatus

        return KIIRecord.objects.filter(assigned_ra=user).exclude(status__in=[KIIStatus.COMPLETED, KIIStatus.DECLINED]).count()
    from .views import open_main_work

    return open_main_work().filter(assigned_ra=user).count()


def new_link_assignee(*, kii: bool = False):
    """Who the next link's case (or KII record) goes to: the named RA with the least open work of that kind."""
    ras = new_link_assignees()
    if not ras:
        return None
    return min(ras, key=lambda u: _open_work(u, kii=kii)) if len(ras) > 1 else ras[0]  # min() keeps the first on a tie


def assign_on_link(subject, *, issued_by=None) -> bool:
    """Put the Main-400 case or KII record whose link was just issued on a named RA's call list. True if it moved."""
    if "duplicate_of" in (subject.metadata or {}):
        return False
    current = subject.assigned_ra
    if current is not None and current.is_active and getattr(current.role, "name", "") == TELEPHONE_RA:
        return False
    kii = hasattr(subject, "kii_id")
    ra = new_link_assignee(kii=kii)
    if ra is None:
        return False
    subject.assigned_ra = ra
    subject.save(update_fields=["assigned_ra", "updated_at"])
    ident = {"study": "KII", "kii_ids": [subject.kii_id]} if kii else {"study": "QUAN", "sample_ids": [subject.sample_id]}
    log_action("ra.assigned", subject, {**ident, "to": ra.username, "from": current.username if current else "unassigned",
                                        "reason": "A link was issued: everyone given a link goes on a research assistant's call list"},
               user=issued_by)
    return True
