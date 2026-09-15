"""
Reports: fieldwork analytics in one payload (added 2026-09-15).

Operational insight only -- progress, reach, timeliness, data quality and
effort. Every figure is a count or a rate over cases; no organisation name,
respondent name or contact detail appears (docs/18), and no answer from the
questionnaire is scored or combined into anything resembling the ABI
(AGENTS.md ground rule 3).

The case funnel counts each case once, at the furthest stage it reached,
from durable evidence: an invitation issued, a link opened, an eligible
respondent, GIVEN consent, the questionnaire handed over, a submission, a
human QA pass. Token status alone can't do this -- a superseded invitation's
status becomes EXPIRED and forgets how far it got -- which is why the
Contact dashboard's token counts drift upward with every reissue.
"""

from collections import Counter
from datetime import timedelta
from statistics import median

from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from apps.consent.models import ConsentDecision, ConsentRecord, ConsentType
from apps.contacts.models import Appointment, ContactEvent, ContactOutcome, Respondent
from apps.costs.models import CostEvent
from apps.evidence.models import DocumentQAStatus, DocumentRecord
from apps.invitations.models import InvitationToken, TokenStatus
from apps.kii.models import KIIRecord, KIIStatus
from apps.kobo.models import AdministrationMode, QAStatus, QUANSubmission
from apps.messaging.models import MessageLog, MessageStatus
from apps.qa.models import QAEvent, QARuleThreshold
from apps.sampling.models import (
    ActorFamily,
    Province,
    ReserveStatus,
    SampleCase,
    SampleType,
    SizeClass,
    WorkflowStatus,
)

MAIN_TARGET = 400
KII_TARGET = 60
DOCUMENT_TARGET_LOW, DOCUMENT_TARGET_HIGH = 50, 75
RANGES = {"7": 7, "30": 30, "90": 90, "all": None}
CACHE_SECONDS = 60

_OPENED = [TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED, TokenStatus.CONSENTED,
           TokenStatus.SURVEY_STARTED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED]
_STARTED = [TokenStatus.SURVEY_STARTED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED]
_WORKFLOW_ORDER = [s.value for s in WorkflowStatus]
DURATION_BUCKETS = [  # (upper bound in minutes, label)
    (5, "Under 5"), (10, "5–10"), (15, "10–15"), (20, "15–20"), (30, "20–30"),
    (45, "30–45"), (60, "45–60"), (90, "60–90"), (None, "Over 90"),
]


def _active_sample():
    """Main cases plus any reserve that has been activated to replace one."""
    return SampleCase.objects.filter(
        Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED)
    )


def _case_flags():
    tokens = InvitationToken.objects.filter(sample_case=OuterRef("pk"))
    rows = _active_sample().annotate(
        f_invited=Exists(tokens),
        t_opened=Exists(tokens.filter(status__in=_OPENED)),
        f_eligible=Exists(Respondent.objects.filter(sample_case=OuterRef("pk"), is_eligible=True)),
        f_consented=Exists(ConsentRecord.objects.filter(
            sample_case=OuterRef("pk"), consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN)),
        t_started=Exists(tokens.filter(status__in=_STARTED)),
        f_submitted=Exists(QUANSubmission.objects.filter(sample_case=OuterRef("pk"))),
        f_passed=Exists(QUANSubmission.objects.filter(sample_case=OuterRef("pk"), qa_status=QAStatus.QA_PASSED)),
    ).values(
        "id", "workflow_status", "organisation__province", "organisation__actor_family", "organisation__size_class",
        "f_invited", "t_opened", "f_eligible", "f_consented", "t_started", "f_submitted", "f_passed",
    )
    opened_from = set(_WORKFLOW_ORDER[_WORKFLOW_ORDER.index("S06"):_WORKFLOW_ORDER.index("S12")])
    started_from = set(_WORKFLOW_ORDER[_WORKFLOW_ORDER.index("S07"):_WORKFLOW_ORDER.index("S12")])
    out = []
    for row in rows:
        # A token's own status forgets its progress once superseded, and a
        # case's workflow status only tracks respondents invited after S03 --
        # either piece of evidence is enough. A submission implies every
        # earlier stage too.
        row["f_opened"] = row["t_opened"] or row["workflow_status"] in opened_from or row["f_submitted"]
        row["f_started"] = row["t_started"] or row["workflow_status"] in started_from or row["f_submitted"]
        out.append(row)
    return out


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def _breakdown(rows, field, choices):
    labels = dict(choices)
    grouped: dict[str, Counter] = {}
    for row in rows:
        key = row[field] or "UNKNOWN"
        counter = grouped.setdefault(key, Counter())
        counter["cases"] += 1
        counter["invited"] += row["f_invited"]
        counter["submitted"] += row["f_submitted"]
        counter["qa_passed"] += row["f_passed"]
    out = [
        {"key": key, "label": labels.get(key, key.replace("_", " ").title()), **counts,
         "response_rate": _rate(counts["submitted"], counts["invited"]),
         # Shares of the group's own cases, so a 25-case group compares fairly with a 376-case one.
         "invited_share": _rate(counts["invited"], counts["cases"]) or 0,
         "submitted_share": _rate(counts["submitted"], counts["cases"]) or 0}
        for key, counts in grouped.items()
    ]
    return sorted(out, key=lambda item: (-item["cases"], item["label"]))


def build_report(range_key: str = "30") -> dict:
    days = RANGES.get(range_key, 30)
    cache_key = f"reports-overview:{range_key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = timezone.now()
    since = now - timedelta(days=days) if days else None
    in_range = (lambda qs, field: qs.filter(**{f"{field}__gte": since})) if since else (lambda qs, field: qs)

    rows = _case_flags()
    total = len(rows)
    count = lambda flag: sum(1 for r in rows if r[flag])  # noqa: E731
    invited, submitted, passed = count("f_invited"), count("f_submitted"), count("f_passed")

    funnel = [
        {"stage": "sample", "label": "In the sample", "cases": total},
        {"stage": "invited", "label": "Invited", "cases": invited},
        {"stage": "opened", "label": "Opened the link", "cases": count("f_opened")},
        {"stage": "eligible", "label": "Eligible respondent", "cases": count("f_eligible")},
        {"stage": "consented", "label": "Consented", "cases": count("f_consented")},
        {"stage": "started", "label": "Started questionnaire", "cases": count("f_started")},
        {"stage": "submitted", "label": "Submitted", "cases": submitted},
        {"stage": "qa_passed", "label": "Passed QA", "cases": passed},
    ]

    workflow_counts = dict(
        SampleCase.objects.filter(sample_type=SampleType.MAIN).values_list("workflow_status").annotate(n=Count("id"))
    )
    workflow = [
        {"status": s.value, "label": s.label, "cases": workflow_counts.get(s.value, 0)} for s in WorkflowStatus
    ]

    submissions = in_range(QUANSubmission.objects.all(), "submitted_at")
    local_dates = [timezone.localtime(ts).date() for ts in submissions.values_list("submitted_at", flat=True)]
    by_day = Counter(local_dates)
    if days:
        start = timezone.localdate() - timedelta(days=days - 1)
    else:
        start = min([*local_dates, timezone.localdate() - timedelta(days=29)])
    span = (timezone.localdate() - start).days + 1
    submissions_by_day = [
        {"date": (start + timedelta(days=i)).isoformat(), "submissions": by_day.get(start + timedelta(days=i), 0)}
        for i in range(max(span, 1))
    ]

    durations = [s // 60 for s in submissions.exclude(completion_seconds=None).values_list("completion_seconds", flat=True)]
    histogram = []
    lower = 0
    for upper, label in DURATION_BUCKETS:
        n = sum(1 for d in durations if d >= lower and (upper is None or d < upper))
        histogram.append({"bucket": label, "min_minutes": lower, "max_minutes": upper, "submissions": n})
        lower = upper or lower
    thresholds = {t.code: t.value for t in QARuleThreshold.objects.filter(
        code__in=["min_plausible_duration_seconds", "max_plausible_duration_seconds"])}

    mode_labels = dict(AdministrationMode.choices)
    modes = [
        {"code": row["administration_mode"], "label": mode_labels.get(row["administration_mode"], "Not recorded"),
         "submissions": row["n"]}
        for row in submissions.values("administration_mode").annotate(n=Count("id")).order_by("-n")
    ]

    # QARuleThreshold mode_imbalance_alert_ratio: configured since Phase 0 but
    # never evaluated anywhere until 2026-09-15.
    ratio_row = QARuleThreshold.objects.filter(code="mode_imbalance_alert_ratio").first()
    ratio = float(ratio_row.value) if ratio_row else None
    mode_total = sum(m["submissions"] for m in modes)
    top_mode = modes[0] if modes else None
    mode_imbalance = {
        "threshold": ratio,
        "dominant_mode": top_mode["label"] if top_mode else None,
        "share": _rate(top_mode["submissions"], mode_total) if top_mode else None,
        # Too few submissions to call a skew until there are at least ten.
        "alert": bool(top_mode and ratio and mode_total >= 10 and top_mode["submissions"] / mode_total > ratio),
    }

    qa_labels = dict(QAStatus.choices)
    qa_outcomes = {row["qa_status"]: row["n"] for row in submissions.values("qa_status").annotate(n=Count("id"))}
    qa_flags = [
        {"rule": row["rule_triggered"], "count": row["n"]}
        for row in in_range(QAEvent.objects.filter(reviewer=None), "created_at")
        .values("rule_triggered").annotate(n=Count("id")).order_by("-n")
    ]

    contact_labels = dict(ContactOutcome.choices)
    contacts = in_range(ContactEvent.objects.all(), "occurred_at")
    contact_outcomes = [
        {"outcome": row["outcome"], "label": contact_labels.get(row["outcome"], row["outcome"]), "count": row["n"]}
        for row in contacts.values("outcome").annotate(n=Count("id")).order_by("-n")
    ]

    kii_labels = dict(KIIStatus.choices)
    kii_counts = dict(KIIRecord.objects.values_list("status").annotate(n=Count("id")))
    doc_labels = dict(DocumentQAStatus.choices)
    doc_counts = dict(DocumentRecord.objects.values_list("qa_status").annotate(n=Count("id")))

    total_cost = CostEvent.objects.aggregate(total=Sum("amount"))["total"] or 0

    report = {
        "generated_at": now.isoformat(),
        "range": {"key": range_key if range_key in RANGES else "30", "days": days,
                  "since": since.date().isoformat() if since else None},
        "kpis": {
            "sample_target": MAIN_TARGET,
            "active_sample": total,
            "cases_invited": invited,
            "cases_submitted": submitted,
            "cases_qa_passed": passed,
            "response_rate": _rate(submitted, invited),
            "completion_rate": _rate(passed, MAIN_TARGET),
            "median_completion_minutes": round(median(durations), 1) if durations else None,
            "submissions_in_range": len(local_dates),
            "follow_ups_sent_in_range": in_range(
                MessageLog.objects.filter(status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]), "created_at").count(),
            "withdrawals": ConsentRecord.objects.filter(
                consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.WITHDRAWN).values("sample_case").distinct().count(),
            "reserves_activated": SampleCase.objects.filter(sample_type=SampleType.RESERVE, status=ReserveStatus.ACTIVATED).count(),
            "kii_completed": kii_counts.get(KIIStatus.COMPLETED, 0),
            "kii_target": KII_TARGET,
            "documents_included": doc_counts.get(DocumentQAStatus.INCLUDED, 0),
            "documents_target_low": DOCUMENT_TARGET_LOW,
            "documents_target_high": DOCUMENT_TARGET_HIGH,
            "cost_total": str(total_cost),
            "cost_per_qa_passed": str(round(total_cost / passed, 2)) if passed else None,
        },
        "funnel": funnel,
        "workflow": workflow,
        "submissions_by_day": submissions_by_day,
        "breakdowns": {
            "province": _breakdown(rows, "organisation__province", Province.choices),
            "actor_family": _breakdown(rows, "organisation__actor_family", ActorFamily.choices),
            "size_class": _breakdown(rows, "organisation__size_class", SizeClass.choices),
        },
        "administration_modes": modes,
        "mode_imbalance": mode_imbalance,
        "duration_histogram": histogram,
        "duration_thresholds_minutes": {
            "min": (thresholds.get("min_plausible_duration_seconds") or 0) / 60 or None,
            "max": (thresholds.get("max_plausible_duration_seconds") or 0) / 60 or None,
        },
        "qa": {
            "outcomes": [{"status": s, "label": qa_labels[s], "count": qa_outcomes.get(s, 0)} for s in qa_labels],
            "flags": qa_flags,
        },
        "contact": {
            "outcomes": contact_outcomes,
            "appointments": [
                {"status": row["status"], "count": row["n"]}
                for row in Appointment.objects.values("status").annotate(n=Count("id")).order_by("status")
            ],
        },
        "kii": [{"status": s, "label": kii_labels[s], "count": kii_counts.get(s, 0)} for s in kii_labels],
        "documents": [{"status": s, "label": doc_labels[s], "count": doc_counts.get(s, 0)} for s in doc_labels],
    }
    cache.set(cache_key, report, CACHE_SECONDS)
    return report
