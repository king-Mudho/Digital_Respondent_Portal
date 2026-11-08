import csv

from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageRATeam, CanUseCalls, CanViewOwnRAWork
from apps.audit.utils import log_action

from . import credit as credits
from .administer import AdministerError, administer_kii, administer_main
from .models import CreditKind, Study, SubmissionCredit
from .roles import RA_ROLES, TELEPHONE_RA


def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


def _period(request, credits_qs):
    """?since=YYYY-MM-DD&until=YYYY-MM-DD narrows credits to a pay period (by submission date)."""
    since, until = parse_date(request.query_params.get("since") or ""), parse_date(request.query_params.get("until") or "")
    if since:
        credits_qs = credits_qs.filter(submitted_at__date__gte=since)
    if until:
        credits_qs = credits_qs.filter(submitted_at__date__lte=until)
    return credits_qs


def _credit_row(c: SubmissionCredit) -> dict:
    if c.study == Study.QUAN:
        case = c.sample_case
        ref, org = case.sample_id, case.organisation.name
        qa = c.quan_submission.get_qa_status_display() if c.quan_submission_id else ""
    else:
        from apps.contacts.kii_finder import organisation_name

        ref, org, qa = c.kii_record.kii_id, organisation_name(c.kii_record), ""
    return {
        "id": c.id, "study": c.study, "study_label": c.get_study_display(), "ref": ref, "organisation": org,
        "submitted_at": c.submitted_at, "kind": c.kind, "kind_label": c.get_kind_display(),
        "ra": c.ra.username if c.ra_id else "", "ra_name": (c.ra.get_full_name() or c.ra.username) if c.ra_id else "",
        "evidence": c.evidence, "qa_status": qa, "overridden": c.overridden_at is not None, "override_reason": c.override_reason,
        "overridden_by": c.overridden_by.username if c.overridden_by_id else "",
    }


def _credits_qs():
    return SubmissionCredit.objects.select_related("ra__role", "sample_case__organisation", "kii_record", "quan_submission",
                                                    "overridden_by")


def _workload(user) -> dict:
    """What is assigned to this RA, and how far it got."""
    from apps.contacts.models import CALL_CHANNELS, ContactEvent
    from apps.kii.models import KIIRecord
    from apps.sampling.models import SampleCase

    week = timezone.now() - timezone.timedelta(days=7)
    cases = SampleCase.objects.filter(assigned_ra=user)
    records = KIIRecord.objects.filter(assigned_ra=user)
    return {
        "main_assigned": cases.count(), "kii_assigned": records.count(),
        "main_by_status": dict(cases.values_list("workflow_status").annotate(n=Count("id"))),
        "kii_by_status": dict(records.values_list("status").annotate(n=Count("id"))),
        "calls_7d": ContactEvent.objects.filter(ra=user, channel__in=CALL_CHANNELS, occurred_at__gte=week).count(),
        "contacts_7d": ContactEvent.objects.filter(ra=user, occurred_at__gte=week).count(),
    }


class MyWorkView(APIView):
    """GET /api/v1/ra/my-work/?since=&until= -- an RA's own assigned work and every completion credited to them, with
    the numbers they are paid on. Never another RA's."""

    permission_classes = [CanViewOwnRAWork]

    def get(self, request):
        credits.refresh()
        mine = _period(request, _credits_qs().filter(ra=request.user))
        summary = credits.summary(mine)
        return Response({"name": request.user.get_full_name() or request.user.username, "workload": _workload(request.user),
                         "totals": summary[0] if summary else None, "credits": [_credit_row(c) for c in mine],
                         "assist_days": credits.settings.RA_ASSIST_CREDIT_DAYS})


class TeamView(APIView):
    """GET /api/v1/ra/team/?since=&until=[&download=csv] -- every RA's workload and credited completions (the pay
    sheet), and the latest completions with who earned them. CSV for paying. PI, Field Coordinator; Supervisor reads."""

    permission_classes = [CanManageRATeam]

    def get(self, request):
        from apps.accounts.models import User
        from apps.kii.models import KIIRecord, KIIStatus

        credits.refresh()
        period = _period(request, _credits_qs())
        if request.query_params.get("download") == "csv":  # not ?format=, which DRF reads as a renderer
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="ABF-FST_RA_completions.csv"'
            writer = csv.writer(response)
            writer.writerow(["Submitted", "Study", "Case / KII", "Organisation", "Research assistant", "Credit", "Evidence",
                             "QA status", "Changed by PI"])
            for c in period:
                row = _credit_row(c)
                writer.writerow([timezone.localtime(c.submitted_at).strftime("%Y-%m-%d %H:%M"), row["study_label"], row["ref"],
                                 row["organisation"], row["ra_name"] or "-", row["kind_label"], row["evidence"], row["qa_status"],
                                 row["override_reason"]])
            log_action("ra.pay_sheet_downloaded", request.user, {"since": request.query_params.get("since"),
                                                                 "until": request.query_params.get("until")}, user=request.user)
            return response
        summary = {r["ra_id"]: r for r in credits.summary(period)}
        ras = User.objects.filter(role__name__in=RA_ROLES, is_active=True).select_related("role").order_by("username")
        team = [{"id": u.id, "username": u.username, "name": u.get_full_name() or u.username, "role": u.role.name,
                 "role_label": u.role.get_name_display(), "workload": _workload(u),
                 "credits": summary.get(u.id, {"quan_administered": 0, "quan_assisted": 0, "kii_administered": 0,
                                               "kii_assisted": 0, "quan_qa_passed": 0, "total": 0})} for u in ras]
        others = [r for ra_id, r in summary.items() if ra_id not in {u.id for u in ras}]  # e.g. the PI administered one
        return Response({
            "team": team, "others": others,
            "uncredited": period.filter(kind=CreditKind.UNCREDITED).count(),
            "credits": [_credit_row(c) for c in period[:300]],
            "unassigned": {"main": open_main_work().filter(assigned_ra=None).count(),
                           "kii": KIIRecord.objects.filter(assigned_ra=None).exclude(
                               status__in=[KIIStatus.COMPLETED, KIIStatus.DECLINED]).count()},
            # Who holds the open Main-400 work now, to move it from (2026-11-08).
            "main_holders": [{"id": h["assigned_ra"], "username": h["assigned_ra__username"], "count": h["n"]}
                             for h in open_main_work().exclude(assigned_ra=None).values("assigned_ra", "assigned_ra__username")
                             .annotate(n=Count("id")).order_by("-n")],
            "assist_days": credits.settings.RA_ASSIST_CREDIT_DAYS,
            "can_override": getattr(request.user.role, "name", "") == "PI_ADMIN",
        })


CLOSED_WORKFLOW = ["S08", "S09", "S10", "S11", "S12", "S13", "S14"]


def open_main_work():
    """Main-400 cases and activated Reserves still to be completed -- what a research assistant can be given."""
    from django.db.models import Q

    from apps.sampling.models import SampleCase, SampleType

    return (SampleCase.objects.filter(Q(sample_type=SampleType.MAIN) | Q(sample_type=SampleType.RESERVE, status="ACTIVATED"))
            .exclude(workflow_status__in=CLOSED_WORKFLOW).exclude(metadata__has_key="duplicate_of"))


class AssignMainView(APIView):
    """POST /api/v1/ra/assign-main/ {ra_id|null, from: "unassigned"|<user id>, limit?, sample_ids?, preview?} -- give open
    Main-400 cases and activated Reserves to an RA, from the unassigned ones or from another account (most open work
    sat on one shared Contact RA account). Audited."""

    permission_classes = [CanManageRATeam]

    def post(self, request):
        from apps.accounts.models import User

        from .roles import ASSIGNED_CASE_ROLES

        data = request.data
        ra = None
        if data.get("ra_id") not in (None, ""):
            ra = User.objects.filter(pk=data.get("ra_id"), role__name__in=ASSIGNED_CASE_ROLES, is_active=True).first()
            if ra is None:
                return _error("invalid_input", "Cases go to an active Contact RA or Research Assistant (calls) account.")
        cases = open_main_work().order_by("sample_id")
        if isinstance(data.get("sample_ids"), list):
            cases = cases.filter(sample_id__in=data["sample_ids"])
        elif data.get("from") == "unassigned":
            cases = cases.filter(assigned_ra=None)
        elif str(data.get("from", "")).isdigit():
            cases = cases.filter(assigned_ra_id=int(data["from"]))
        else:
            return _error("invalid_input", "Choose where the cases come from.")
        try:
            limit = int(data["limit"]) if data.get("limit") not in (None, "") else None
        except (TypeError, ValueError):
            return _error("invalid_input", "The number of cases must be a number.")
        ids = list(cases.values_list("sample_id", flat=True))[:limit] if limit else list(cases.values_list("sample_id", flat=True))
        if not data.get("preview"):
            from apps.sampling.models import SampleCase

            SampleCase.objects.filter(sample_id__in=ids).update(assigned_ra=ra)
            log_action("ra.assigned", request.user, {"study": "QUAN", "to": ra.username if ra else None,
                                                     "from": data.get("from"), "sample_ids": ids}, user=request.user)
        return Response({"count": len(ids), "sample_ids": ids})


class AssignKIIView(APIView):
    """POST /api/v1/ra/assign-kii/ {ra_id|null, kii_ids?: [...], from_unassigned?: true, limit?} -- give KII records to a
    Research Assistant (calls), or take them back. Main-400 cases use sample-cases/bulk-assign/."""

    permission_classes = [CanManageRATeam]

    def post(self, request):
        from apps.accounts.models import User
        from apps.kii.models import KIIRecord, KIIStatus

        data = request.data
        ra = None
        if data.get("ra_id") not in (None, ""):
            ra = User.objects.filter(pk=data.get("ra_id"), role__name=TELEPHONE_RA, is_active=True).first()
            if ra is None:
                return _error("invalid_input", "KII records go to an active Research Assistant (calls) account.")
        records = KIIRecord.objects.exclude(status__in=[KIIStatus.COMPLETED, KIIStatus.DECLINED]).order_by("kii_id")
        if isinstance(data.get("kii_ids"), list):
            records = records.filter(kii_id__in=data["kii_ids"])
        elif data.get("from_unassigned"):
            records = records.filter(assigned_ra=None)
        else:
            return _error("invalid_input", "Name the KII records, or take them from the unassigned ones.")
        try:
            limit = int(data["limit"]) if data.get("limit") not in (None, "") else None
        except (TypeError, ValueError):
            return _error("invalid_input", "The number of records must be a number.")
        ids = list(records.values_list("kii_id", flat=True)[:limit] if limit else records.values_list("kii_id", flat=True))
        if not data.get("preview"):
            KIIRecord.objects.filter(kii_id__in=ids).update(assigned_ra=ra, updated_at=timezone.now())
            log_action("ra.assigned", request.user, {"study": "KII", "to": ra.username if ra else None, "kii_ids": ids},
                       user=request.user)
        return Response({"count": len(ids), "kii_ids": ids})


class CreditOverrideView(APIView):
    """POST /api/v1/ra/credits/<id>/override/ {ra_id|null, kind, reason} -- the PI settles a credit by hand."""

    permission_classes = [CanManageRATeam]

    def post(self, request, pk):
        from apps.accounts.models import User

        if getattr(request.user.role, "name", "") != "PI_ADMIN":
            return _error("forbidden", "Only the PI changes a credit.", 403)
        credit = get_object_or_404(SubmissionCredit, pk=pk)
        ra = User.objects.filter(pk=request.data.get("ra_id")).first() if request.data.get("ra_id") not in (None, "") else None
        try:
            credits.override(credit, ra=ra, kind=str(request.data.get("kind", "")), reason=str(request.data.get("reason", "")),
                             user=request.user)
        except ValueError as exc:
            return _error("invalid_input", str(exc))
        return Response(_credit_row(credit))


class AdministerView(APIView):
    """POST /api/v1/ra/administer/<main|kii>/<SID-.../KII-...>/ {mode: PHONE|WHATSAPP_CALL, respondent_name?,
    role_category?, information_sheet_version, recording_consent?} -- the RA confirms the respondent's verbal consent
    (and, for the questionnaire, who they are), and gets the form link stamped with their name. Calls' people only."""

    permission_classes = [CanUseCalls]

    def post(self, request, kind, ident):
        if getattr(request.user.role, "name", "") == "SUPERVISOR_READONLY":
            return _error("forbidden", "Your role can read but not administer forms.", 403)
        d = request.data
        try:
            if kind == "main":
                url = administer_main(request.user, ident, mode=str(d.get("mode", "")), respondent_name=str(d.get("respondent_name", "")),
                                      role_category=str(d.get("role_category", "")),
                                      information_sheet_version=str(d.get("information_sheet_version", "")))
            elif kind == "kii":
                url = administer_kii(request.user, ident, mode=str(d.get("mode", "")),
                                     information_sheet_version=str(d.get("information_sheet_version", "")),
                                     recording_consent=bool(d.get("recording_consent")))
            else:
                return _error("not_found", "Unknown study.", 404)
        except AdministerError as exc:
            return _error(exc.code, str(exc), exc.status)
        return Response({"kobo_form_url": url})
