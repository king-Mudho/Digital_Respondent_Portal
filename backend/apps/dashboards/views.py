"""
Six read-only aggregate dashboards (docs/16_DASHBOARDS_AND_REPORTING.md).
Never expose Organisation.name, Respondent.full_name, or unbanded financial
figures (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md) -- every payload here is
counts/aggregates only, verified by
tests/test_dashboards.py::test_dashboards_never_expose_identifying_fields.
"""

from datetime import date

from django.db.models import Count, Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAnalystOrAdmin, IsQAOrAdmin
from apps.contacts.models import Appointment, ContactEvent, Respondent
from apps.costs.models import CostEvent
from apps.evidence.models import DocumentQAStatus, DocumentRecord
from apps.invitations.models import InvitationToken, TokenStatus
from apps.kii.models import KIIRecord, KIIStatus
from apps.kobo.models import QAStatus as SubmissionQAStatus
from apps.kobo.models import QUANSubmission
from apps.qa.models import QAEvent
from apps.sampling.models import SampleCase, SampleType

DATA_LOCK_DATE = date(2026, 11, 30)
MAIN_TARGET = 400
KII_TARGET = 60
DOCUMENT_TARGET_LOW, DOCUMENT_TARGET_HIGH = 50, 75

# InvitationToken.status is a monotonically-advancing funnel field (see
# apps.invitations.services.advance_token_status) -- a token currently at
# CONSENTED has necessarily already been sent and opened, but an exact
# `status="SENT"` filter would never count it. "Sent" and "opened" here
# mean "reached at least this stage", i.e. the current status is this one
# or any later one in the funnel (excluding the terminal EXPIRED/REVOKED,
# which -- by this system's design -- do not retain which stage they'd
# reached before terminating).
_SENT_OR_LATER = [
    TokenStatus.SENT, TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED,
    TokenStatus.CONSENTED, TokenStatus.SURVEY_STARTED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED,
]
_OPENED_OR_LATER = [
    TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED,
    TokenStatus.CONSENTED, TokenStatus.SURVEY_STARTED, TokenStatus.SUBMITTED, TokenStatus.QA_PASSED,
]


class ExecutiveDashboardView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        quan_completed = QUANSubmission.objects.filter(qa_status=SubmissionQAStatus.QA_PASSED).count()
        kii_completed = KIIRecord.objects.filter(status=KIIStatus.COMPLETED).count()
        documents_coded = DocumentRecord.objects.filter(qa_status=DocumentQAStatus.INCLUDED).count()
        days_remaining = (DATA_LOCK_DATE - date.today()).days
        total_cost = CostEvent.objects.aggregate(total=Sum("amount"))["total"] or 0

        gaps = list(
            SampleCase.objects.filter(sample_type=SampleType.MAIN)
            .values("stratum__province", "stratum__actor_family", "stratum__value_chain", "stratum__size_class")
            .annotate(count=Count("id"))
            .order_by("count")[:5]
        )

        return Response({
            "quan_completed": quan_completed,
            "quan_target": MAIN_TARGET,
            "kii_completed": kii_completed,
            "kii_target": KII_TARGET,
            "documents_coded": documents_coded,
            "documents_target_low": DOCUMENT_TARGET_LOW,
            "documents_target_high": DOCUMENT_TARGET_HIGH,
            "days_remaining_to_data_lock": days_remaining,
            "fieldwork_expenditure_to_date": str(total_cost),
            "highest_risk_coverage_gaps": gaps,
        })


class SamplingDashboardView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        by_stratum = list(
            SampleCase.objects.filter(sample_type=SampleType.MAIN)
            .values("stratum__code")
            .annotate(
                verified_count=Count("id", filter=Q(organisation__verification_status="VERIFIED")),
                total=Count("id"),
            )
        )
        by_province = list(
            SampleCase.objects.filter(sample_type=SampleType.MAIN)
            .values("stratum__province")
            .annotate(count=Count("id"))
        )
        reserve_activations = list(
            SampleCase.objects.filter(sample_type=SampleType.RESERVE, status="ACTIVATED")
            .values("activation_reason")
            .annotate(count=Count("id"))
        )

        return Response({
            "main_by_province": by_province,
            "main_by_stratum": by_stratum,
            "reserve_activations_by_reason": reserve_activations,
        })


class ContactDashboardView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        organisations_verified = SampleCase.objects.filter(
            sample_type=SampleType.MAIN, organisation__verification_status="VERIFIED"
        ).count()
        eligible_respondents = Respondent.objects.filter(is_eligible=True).count()
        invitations_sent = InvitationToken.objects.filter(status__in=_SENT_OR_LATER).count()
        invitations_opened = InvitationToken.objects.filter(status__in=_OPENED_OR_LATER).count()
        appointments_upcoming = Appointment.objects.filter(status__in=["REQUESTED", "CONFIRMED"]).count()
        refusals = ContactEvent.objects.filter(outcome="REFUSED").count()
        unreachable = ContactEvent.objects.filter(outcome="WRONG_NUMBER").count()

        return Response({
            "organisations_verified": organisations_verified,
            "eligible_respondents_identified": eligible_respondents,
            "invitations_sent": invitations_sent,
            "invitations_opened": invitations_opened,
            "appointments_upcoming": appointments_upcoming,
            "refusals": refusals,
            "unreachable_cases": unreachable,
        })


class QADashboardView(APIView):
    permission_classes = [IsQAOrAdmin]

    def get(self, request):
        today_count = QUANSubmission.objects.filter(submitted_at__date=date.today()).count()
        cumulative = QUANSubmission.objects.count()
        mode_distribution = dict(
            QUANSubmission.objects.values_list("administration_mode").annotate(count=Count("id"))
        )
        qa_queue_open = QUANSubmission.objects.filter(
            qa_status__in=[SubmissionQAStatus.PENDING, SubmissionQAStatus.QUERY]
        ).count()

        return Response({
            "submissions_today": today_count,
            "submissions_cumulative": cumulative,
            "mode_distribution": mode_distribution,
            "qa_queue_open": qa_queue_open,
            "qa_events_recorded": QAEvent.objects.count(),
        })


class KIIDocumentDashboardView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        kii_by_status = dict(KIIRecord.objects.values_list("status").annotate(count=Count("id")))
        kii_by_category = list(
            KIIRecord.objects.values("stakeholder_category").annotate(count=Count("id"))
        )
        documents_by_type = dict(DocumentRecord.objects.values_list("document_type").annotate(count=Count("id")))
        documents_by_qa_status = dict(DocumentRecord.objects.values_list("qa_status").annotate(count=Count("id")))

        return Response({
            "kii_completed": kii_by_status.get(KIIStatus.COMPLETED, 0),
            "kii_target": KII_TARGET,
            "kii_by_status": kii_by_status,
            "kii_by_stakeholder_category": kii_by_category,
            "documents_by_type": documents_by_type,
            "documents_by_qa_status": documents_by_qa_status,
            "documents_target_low": DOCUMENT_TARGET_LOW,
            "documents_target_high": DOCUMENT_TARGET_HIGH,
        })


class CostDashboardView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        by_category = list(CostEvent.objects.values("category").annotate(total=Sum("amount")))
        total_cost = CostEvent.objects.aggregate(total=Sum("amount"))["total"] or 0
        qa_passed_count = QUANSubmission.objects.filter(qa_status=SubmissionQAStatus.QA_PASSED).count()
        kii_completed_count = KIIRecord.objects.filter(status=KIIStatus.COMPLETED).count()

        cost_per_qa_passed = float(total_cost) / qa_passed_count if qa_passed_count else None
        cost_per_kii = float(total_cost) / kii_completed_count if kii_completed_count else None

        return Response({
            "total_cost": str(total_cost),
            "cost_by_category": by_category,
            "cost_per_qa_passed_quan": cost_per_qa_passed,
            "cost_per_completed_kii": cost_per_kii,
        })
