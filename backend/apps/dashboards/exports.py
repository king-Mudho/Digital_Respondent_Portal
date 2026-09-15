"""
De-identified analysis export vs. full operational export
(docs/06_API_ARCHITECTURE.md, docs/16_DASHBOARDS_AND_REPORTING.md). The
schema difference is deliberate: the analysis export excludes every
contact-identifying field entirely (not masked -- absent), while the
operational export includes them for internal operations use only, never
distributed externally (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md).
"""

import csv

from django.http import HttpResponse
from rest_framework.views import APIView

from api.permissions import CanExportDeidentified, IsAdminOnly
from apps.audit.utils import log_action
from apps.kobo.models import QUANSubmission


class _ExportRow:
    """log_action() needs an object with a .pk; an export isn't tied to one
    row, so this names the export run itself."""

    def __init__(self, name):
        self.pk = name


ANALYSIS_FIELDS = [
    "sample_id",
    "master_id",
    "province",
    "actor_family",
    "value_chain",
    "size_class",
    "administration_mode",
    "qa_status",
    "submitted_at",
    "completion_seconds",
]

# PI decision, 15 Sep 2026: a participant who withdraws after submitting keeps
# their answers archived (audit trail) but is left out of analysis. The
# analysis export therefore omits them entirely; the operational export keeps
# every row and says which ones are withdrawn.
OPERATIONAL_EXTRA_FIELDS = [
    "consent_withdrawn",
    "organisation_name",
    "respondent_full_name",
    "respondent_phone",
    "respondent_email",
    "gatekeeper_name",
    "gatekeeper_contact",
]


def _submissions():
    """Submissions with everything a row needs, in one query: the case's
    latest participation-consent decision is annotated rather than looked up
    per row (the export ran one consent query per submission)."""
    from django.db.models import OuterRef, Subquery

    from apps.consent.models import ConsentRecord, ConsentType

    latest_decision = (
        ConsentRecord.objects.filter(sample_case=OuterRef("sample_case"), consent_type=ConsentType.PARTICIPATION)
        .order_by("-timestamp")
        .values("decision")[:1]
    )
    return QUANSubmission.objects.select_related("sample_case__organisation").annotate(
        latest_consent_decision=Subquery(latest_decision)
    ).order_by("submitted_at")


def _base_row(submission: QUANSubmission) -> dict:
    case = submission.sample_case
    org = case.organisation
    return {
        "sample_id": case.sample_id,
        "master_id": org.master_id,
        "province": org.province,
        "actor_family": org.actor_family,
        "value_chain": org.value_chain,
        "size_class": org.size_class,
        "administration_mode": submission.administration_mode,
        "qa_status": submission.qa_status,
        "submitted_at": submission.submitted_at.isoformat(),
        "completion_seconds": submission.completion_seconds,
    }


def _is_withdrawn(submission: QUANSubmission) -> bool:
    return getattr(submission, "latest_consent_decision", None) == "WITHDRAWN"


class AnalysisExportView(APIView):
    """GET /api/v1/export/analysis/ -- de-identified CSV. Contact
    identifiers excluded entirely, not just masked. Uses
    CanExportDeidentified, not IsAnalystOrAdmin -- Supervisor has dashboard
    access but docs/18 explicitly excludes it from export."""

    permission_classes = [CanExportDeidentified]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="drp_analysis_export.csv"'
        writer = csv.DictWriter(response, fieldnames=ANALYSIS_FIELDS)
        writer.writeheader()
        left_out = 0
        for submission in _submissions():
            if _is_withdrawn(submission):
                left_out += 1
                continue
            writer.writerow(_base_row(submission))

        log_action("export.analysis_generated", _ExportRow("analysis"),
                   {"requested_by_id": request.user.id, "withdrawn_left_out": left_out})
        return response


class OperationalExportView(APIView):
    """GET /api/v1/export/operational/ -- full CSV including contact data,
    IsAdminOnly, internal operations use only."""

    permission_classes = [IsAdminOnly]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="drp_operational_export.csv"'
        fieldnames = ANALYSIS_FIELDS + OPERATIONAL_EXTRA_FIELDS
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()

        for submission in _submissions().prefetch_related("sample_case__respondents"):
            row = _base_row(submission)
            respondent = next(iter(submission.sample_case.respondents.all()), None)
            row.update({
                "consent_withdrawn": _is_withdrawn(submission),
                "organisation_name": submission.sample_case.organisation.name,
                "respondent_full_name": getattr(respondent, "full_name", ""),
                "respondent_phone": getattr(respondent, "phone", ""),
                "respondent_email": getattr(respondent, "email", ""),
                "gatekeeper_name": getattr(respondent, "gatekeeper_name", ""),
                "gatekeeper_contact": getattr(respondent, "gatekeeper_contact", ""),
            })
            writer.writerow(row)

        log_action("export.operational_generated", _ExportRow("operational"), {"requested_by_id": request.user.id})
        return response
