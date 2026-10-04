"""Contact finder endpoints (apps/contacts/contact_finder.py). The PI's and Field Coordinator's tool, since each run
costs money; Supervisor may read. The AI proposes, a person decides."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFieldCoordinatorOrAdmin

from . import contact_finder as cf
from .models import ContactProposal, ContactSearchRun
from .tasks import search_contacts


class ContactSearchRunSerializer(serializers.ModelSerializer):
    queue_position = serializers.SerializerMethodField()

    class Meta:
        model = ContactSearchRun
        fields = [
            "id", "status", "started_at", "running_since", "finished_at", "provider", "model", "searches_used",
            "summary", "error", "dropped", "queue_position",
        ]

    def get_queue_position(self, run):
        return cf.queue_position(run)


class ContactProposalSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = ContactProposal
        fields = [
            "id", "run", "kind", "kind_label", "value", "person_name", "person_title", "person_email", "person_phone",
            "sources", "confidence", "flags", "status", "reviewed_at", "reject_reason", "respondent",
        ]


def _error(exc: cf.ContactFinderError) -> Response:
    return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)


class ContactSearchView(APIView):
    """GET /api/v1/contacts/{sample_id}/contact-search/ -- the latest run, every finding for the case, and the
    accepted website and office location. POST -- start a search in the background (202)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request, sample_id):
        from apps.sampling.models import SampleCase

        case = get_object_or_404(SampleCase.objects.select_related("organisation"), sample_id=sample_id)
        cf.expire_stale_runs()
        run = case.contact_searches.first()
        proposals = case.contact_proposals.order_by("-run_id", "id")
        return Response({
            "configured": cf.is_configured(),
            "run": ContactSearchRunSerializer(run).data if run else None,
            "proposals": ContactProposalSerializer(proposals, many=True).data,
            "public_contacts": (case.organisation.metadata or {}).get("public_contacts", {}) if case.organisation else {},
        })

    def post(self, request, sample_id):
        from apps.sampling.models import SampleCase

        case = get_object_or_404(SampleCase.objects.select_related("organisation"), sample_id=sample_id)
        try:
            run = cf.start_search(case, user=request.user)
        except cf.ContactFinderError as exc:
            return _error(exc)
        search_contacts.delay(run.pk)
        run.refresh_from_db()
        return Response(ContactSearchRunSerializer(run).data, status=202)


class ContactProposalAcceptView(APIView):
    """POST /api/v1/contacts/contact-proposals/{id}/accept/ {role_category?}"""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        proposal = get_object_or_404(ContactProposal, pk=pk)
        try:
            proposal = cf.accept_proposal(proposal, user=request.user, role_category=str(request.data.get("role_category") or ""))
        except cf.ContactFinderError as exc:
            return _error(exc)
        return Response(ContactProposalSerializer(proposal).data)


class ContactProposalRejectView(APIView):
    """POST /api/v1/contacts/contact-proposals/{id}/reject/ {reason?}"""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def post(self, request, pk):
        proposal = get_object_or_404(ContactProposal, pk=pk)
        try:
            proposal = cf.reject_proposal(proposal, user=request.user, reason=str(request.data.get("reason") or "").strip())
        except cf.ContactFinderError as exc:
            return _error(exc)
        return Response(ContactProposalSerializer(proposal).data)


class ContactSearchBatchView(APIView):
    """GET /api/v1/contacts/contact-search/batch/ -- how many cases have no contact details, the cap, the latest
    batch's progress and the cases with findings waiting for a decision.
    POST {limit} -- queue searches for up to `limit` of them, oldest Sample ID first (refused while a batch runs)."""

    permission_classes = [IsFieldCoordinatorOrAdmin]

    def get(self, request):
        low, high = cf.COST_PER_CASE_USD
        return Response({
            "configured": cf.is_configured(), "without_contacts": cf.cases_without_contacts().count(),
            "max": cf.batch_limit_max(), "cost_per_case_usd": [low, high], **cf.batch_status(),
        })

    def post(self, request):
        try:
            limit = int(request.data.get("limit", 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            runs = cf.start_batch(limit, user=request.user)
        except cf.ContactFinderError as exc:
            return _error(exc)
        for run in runs:
            search_contacts.delay(run.pk)
        low, high = cf.COST_PER_CASE_USD
        return Response({
            "queued": len(runs), "without_contacts": cf.cases_without_contacts().count(),
            "estimated_cost_usd": [round(len(runs) * low, 2), round(len(runs) * high, 2)],
        }, status=202)
