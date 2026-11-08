"""Crediting each completed submission to the research assistant who earned it (PI, 8 Nov 2026). See models.py for
the three kinds. refresh() is run after every KoboToolbox reconciliation and KII form sync, and before the credit
screens are read; it is idempotent, and never touches a credit the PI has overridden.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.utils import log_action

from .models import CreditKind, Study, SubmissionCredit
from .roles import RA_ROLES


def _when(value) -> str:
    return timezone.localtime(value).strftime("%d %b %Y %H:%M") if value else ""


def last_ra_contact(*, sample_case=None, kii_record=None, before):
    """(user, when, what) for the latest contact an RA logged or sent before `before`, within the assist window --
    calls and other contacts they logged, and messages the portal sent in their name. None if there is none."""
    from apps.contacts.models import ContactEvent
    from apps.messaging.models import ProviderMessage

    since = before - timedelta(days=settings.RA_ASSIST_CREDIT_DAYS)
    link = {"sample_case": sample_case} if sample_case is not None else {"kii_record": kii_record}
    found = []
    event = (ContactEvent.objects.filter(**link, ra__role__name__in=RA_ROLES, occurred_at__lte=before, occurred_at__gte=since)
             .select_related("ra").order_by("-occurred_at").first())
    if event:
        found.append((event.ra, event.occurred_at, f"{event.get_channel_display()} {_when(event.occurred_at)}: {event.get_outcome_display()}"))
    message = (ProviderMessage.objects.filter(**link, sent_by__role__name__in=RA_ROLES, created_at__lte=before, created_at__gte=since)
               .select_related("sent_by").order_by("-created_at").first())
    if message:
        found.append((message.sent_by, message.created_at,
                       f"{message.get_channel_display()} {message.get_purpose_display().lower()} sent {_when(message.created_at)}"))
    return max(found, key=lambda f: f[1]) if found else None


def _decide(*, administered_by, sample_case=None, kii_record=None, submitted_at) -> dict:
    if administered_by is not None:
        return {"ra": administered_by, "kind": CreditKind.ADMINISTERED, "evidence": "Filled in with the respondent from the portal",
                "evidence_at": submitted_at}
    contact = last_ra_contact(sample_case=sample_case, kii_record=kii_record, before=submitted_at)
    if contact:
        user, when, what = contact
        return {"ra": user, "kind": CreditKind.ASSISTED, "evidence": what[:300], "evidence_at": when}
    return {"ra": None, "kind": CreditKind.UNCREDITED,
            "evidence": f"No RA contact in the {settings.RA_ASSIST_CREDIT_DAYS} days before it was submitted", "evidence_at": None}


def _kii_submitted_at(record):
    from apps.kobo.models import KoboFormSubmission

    copy = KoboFormSubmission.objects.filter(form_key="kii", record=record.kii_id).exclude(submitted_at=None).order_by("submitted_at").first()
    return copy.submitted_at if copy else record.updated_at


@transaction.atomic
def refresh() -> dict:
    """Create or update the credit of every completed questionnaire and KII. Returns {"created", "updated"}."""
    from apps.kii.models import KIIRecord, KIIStatus
    from apps.kobo.models import QUANSubmission

    created = updated = 0
    overridden_q = set(SubmissionCredit.objects.exclude(overridden_at=None).exclude(quan_submission=None).values_list("quan_submission_id", flat=True))
    overridden_k = set(SubmissionCredit.objects.exclude(overridden_at=None).exclude(kii_record=None).values_list("kii_record_id", flat=True))
    jobs = []
    for s in QUANSubmission.objects.exclude(pk__in=overridden_q).select_related("sample_case", "ra"):
        jobs.append(({"quan_submission": s}, {"study": Study.QUAN, "sample_case": s.sample_case, "submitted_at": s.submitted_at,
                     **_decide(administered_by=s.ra, sample_case=s.sample_case, submitted_at=s.submitted_at)}))
    for r in KIIRecord.objects.filter(status=KIIStatus.COMPLETED).exclude(pk__in=overridden_k).select_related("interviewer"):
        at = _kii_submitted_at(r)
        jobs.append(({"kii_record": r}, {"study": Study.KII, "sample_case": None, "submitted_at": at,
                     **_decide(administered_by=r.interviewer, kii_record=r, submitted_at=at)}))
    for key, values in jobs:
        credit = SubmissionCredit.objects.filter(**key).first()
        if credit is None:
            credit = SubmissionCredit.objects.create(**key, **values)
            created += 1
            log_action("ra_credit.recorded", credit, {"study": credit.study, "kind": credit.kind,
                                                      "ra": credit.ra.username if credit.ra_id else None}, user=None)
        elif any(getattr(credit, f) != v for f, v in values.items()):
            before = (credit.ra_id, credit.kind)
            for f, v in values.items():
                setattr(credit, f, v)
            credit.save()
            updated += 1
            if before != (credit.ra_id, credit.kind):
                log_action("ra_credit.changed", credit, {"study": credit.study, "kind": credit.kind,
                                                         "ra": credit.ra.username if credit.ra_id else None}, user=None)
    return {"created": created, "updated": updated}


def override(credit: SubmissionCredit, *, ra, kind: str, reason: str, user) -> SubmissionCredit:
    """The PI settles a credit by hand (a disputed or mis-recorded one), with a reason. Audited; never recomputed."""
    reason = (reason or "").strip()[:300]
    if not reason:
        raise ValueError("Write why this credit is changed.")
    if kind not in CreditKind.values or (kind == CreditKind.UNCREDITED) != (ra is None):
        raise ValueError("Choose an RA for an administered or assisted credit, or none for no credit.")
    before = {"ra": credit.ra.username if credit.ra_id else None, "kind": credit.kind}
    credit.ra, credit.kind = ra, kind
    credit.overridden_by, credit.overridden_at, credit.override_reason = user, timezone.now(), reason
    credit.save()
    log_action("ra_credit.overridden", credit, {"before": before, "after": {"ra": ra.username if ra else None, "kind": kind},
                                                "reason": reason}, user=user)
    return credit


def summary(credits) -> list[dict]:
    """Per person: administered and assisted completions, by study -- the numbers RAs are paid on."""
    rows = {}
    for c in credits.select_related("ra", "quan_submission"):
        if c.ra_id is None:
            continue
        row = rows.setdefault(c.ra_id, {"ra_id": c.ra_id, "username": c.ra.username, "name": c.ra.get_full_name() or c.ra.username,
                                        "role": getattr(c.ra.role, "name", ""), "quan_administered": 0, "quan_assisted": 0,
                                        "kii_administered": 0, "kii_assisted": 0, "quan_qa_passed": 0, "total": 0})
        key = f"{c.study.lower()}_{'administered' if c.kind == CreditKind.ADMINISTERED else 'assisted'}"
        row[key] += 1
        row["total"] += 1
        if c.study == Study.QUAN and c.quan_submission and c.quan_submission.qa_status == "QA_PASSED":
            row["quan_qa_passed"] += 1
    return sorted(rows.values(), key=lambda r: (-r["total"], r["name"]))
