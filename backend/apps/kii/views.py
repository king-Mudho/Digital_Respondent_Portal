from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageKII
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent

from .models import KIIRecord, KIIStatus
from .serializers import KIIRecordSerializer
from .services import (
    InvalidKIITransition,
    KIIRecordingConsentRequired,
    advance_coding_status,
    advance_transcript_status,
    generate_kii_id,
    mark_completed,
    transition_kii_status,
)


class KIIRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/kii/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [CanManageKII]
    serializer_class = KIIRecordSerializer
    filterset_fields = ["status", "stakeholder_category", "transcript_status", "coding_status"]
    search_fields = [
        "kii_id", "participant_name", "participant_role",
        "stakeholder_category", "organisation__name",
    ]
    # KIIRecord has no Meta.ordering -- an unordered queryset makes
    # PageNumberPagination's page boundaries arbitrary, so a record can
    # appear on two pages or on none.
    queryset = KIIRecord.objects.order_by("kii_id")

    def perform_create(self, serializer):
        serializer.save(kii_id=generate_kii_id())


class KIIRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [CanManageKII]
    serializer_class = KIIRecordSerializer
    queryset = KIIRecord.objects.all()


def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


class KIIStatusTransitionView(APIView):
    """POST /api/v1/kii/{id}/status/ -- {"status": "SCHEDULED"|"COMPLETED"|...}.
    Completing with with_recording=true requires separate recording consent
    (AGENTS.md ground rule 6)."""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        new_status = request.data.get("status")
        with_recording = bool(request.data.get("with_recording", False))

        try:
            if new_status == KIIStatus.COMPLETED:
                mark_completed(record, with_recording=with_recording)
            else:
                transition_kii_status(record, new_status)
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        except KIIRecordingConsentRequired as exc:
            return _error("recording_consent_required", str(exc), status=403)

        return Response(KIIRecordSerializer(record).data)


class KIIConsentView(APIView):
    """POST /api/v1/kii/{id}/consent/ -- records participation or recording
    consent, always as a separate row per consent_type."""

    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        consent_type = request.data.get("consent_type")
        decision = request.data.get("decision")
        if consent_type not in ConsentType.values or decision not in ConsentDecision.values:
            return _error("invalid_input", "Invalid consent_type or decision.")

        consent_record = record_consent(
            kii_record=record,
            consent_type=consent_type,
            decision=decision,
            information_sheet_version=request.data.get("information_sheet_version", ""),
            method=request.data.get("method", ConsentMethod.VERBAL_RA_RECORDED),
        )

        if consent_type == ConsentType.PARTICIPATION:
            record.participation_consent = consent_record
            record.save(update_fields=["participation_consent"])
        elif consent_type == ConsentType.KII_RECORDING:
            record.recording_consent = consent_record
            record.save(update_fields=["recording_consent"])

        return Response({"id": consent_record.id, "consent_type": consent_record.consent_type, "decision": consent_record.decision})


class KIITranscriptStatusView(APIView):
    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        try:
            advance_transcript_status(record, request.data.get("transcript_status"))
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(KIIRecordSerializer(record).data)


class KIICodingStatusView(APIView):
    permission_classes = [CanManageKII]

    def post(self, request, pk):
        record = get_object_or_404(KIIRecord, pk=pk)
        try:
            advance_coding_status(record, request.data.get("coding_status"))
        except InvalidKIITransition as exc:
            return _error("invalid_transition", str(exc))
        return Response(KIIRecordSerializer(record).data)
