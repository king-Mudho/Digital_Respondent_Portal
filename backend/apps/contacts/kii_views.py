"""KII contact finder endpoints (apps/contacts/kii_finder.py). CanManageKII: the PI, Field Coordinator and KII RA
search and decide, the Supervisor may read (PI decision 2026-10-04). KII findings have their own accept/reject
endpoints, so the Main-400 ones (finder_views.py, PI and Field Coordinator only) never act on them, and vice versa."""

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageKII

from . import contact_finder as cf
from . import kii_finder as kf
from .finder_views import ContactProposalSerializer, ContactSearchRunSerializer, _error
from .models import ContactProposal
from .tasks import search_contacts


class KIIContactSearchView(APIView):
    """GET /api/v1/contacts/kii/{id}/contact-search/ -- the latest run and every finding for the record.
    POST -- start a search in the background (202)."""

    permission_classes = [CanManageKII]

    def _record(self, pk):
        from apps.kii.models import KIIRecord

        return get_object_or_404(KIIRecord, pk=pk)

    def get(self, request, pk):
        record = self._record(pk)
        cf.expire_stale_runs()
        run = record.contact_searches.first()
        return Response({
            "configured": cf.is_configured(),
            "searchable": record.status in kf.SEARCHABLE_STATUSES,
            "placeholder": kf.is_placeholder(record),
            "organisation": kf.organisation_name(record),
            "run": ContactSearchRunSerializer(run).data if run else None,
            "proposals": ContactProposalSerializer(record.contact_proposals.order_by("-run_id", "id"), many=True).data,
            "public_contacts": (record.metadata or {}).get("public_contacts", {}),
        })

    def post(self, request, pk):
        record = self._record(pk)
        try:
            run = kf.start_search(record, user=request.user)
        except cf.ContactFinderError as exc:
            return _error(exc)
        search_contacts.delay(run.pk)
        run.refresh_from_db()
        return Response(ContactSearchRunSerializer(run).data, status=202)


class KIIContactProposalAcceptView(APIView):
    """POST /api/v1/contacts/kii-proposals/{id}/accept/"""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        proposal = get_object_or_404(ContactProposal, pk=pk, kii_record__isnull=False)
        try:
            proposal = kf.accept_proposal(proposal, user=request.user)
        except cf.ContactFinderError as exc:
            return _error(exc)
        return Response(ContactProposalSerializer(proposal).data)


class KIIContactProposalRejectView(APIView):
    """POST /api/v1/contacts/kii-proposals/{id}/reject/ {reason?}"""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        proposal = get_object_or_404(ContactProposal, pk=pk, kii_record__isnull=False)
        try:
            proposal = kf.reject_proposal(proposal, user=request.user, reason=str(request.data.get("reason") or "").strip())
        except cf.ContactFinderError as exc:
            return _error(exc)
        return Response(ContactProposalSerializer(proposal).data)


class KIIContactSearchBatchView(APIView):
    """GET /api/v1/contacts/kii-contact-search/batch/ -- records with no contact details, the cap, the latest KII
    batch's progress and the records with findings waiting. POST {limit} -- queue searches (one KII batch at a time)."""

    permission_classes = [CanManageKII]

    def get(self, request):
        low, high = cf.COST_PER_CASE_USD
        return Response({
            "configured": cf.is_configured(), "without_contacts": kf.records_without_contacts().count(),
            "max": cf.batch_limit_max(), "cost_per_case_usd": [low, high], **kf.batch_status(),
        })

    def post(self, request):
        try:
            limit = int(request.data.get("limit", 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            runs = kf.start_batch(limit, user=request.user)  # queues the searches itself, once they are saved
        except cf.ContactFinderError as exc:
            return _error(exc)
        low, high = cf.COST_PER_CASE_USD
        return Response({
            "queued": len(runs), "without_contacts": kf.records_without_contacts().count(),
            "estimated_cost_usd": [round(len(runs) * low, 2), round(len(runs) * high, 2)],
        }, status=202)
