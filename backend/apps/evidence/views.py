from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageDocuments

from .models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord
from .serializers import DocumentRecordSerializer
from .services import (
    DocumentWorkflowError,
    generate_document_id,
    record_authenticity_assessment,
    set_qa_status,
)


class DocumentRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/documents/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [CanManageDocuments]
    serializer_class = DocumentRecordSerializer
    filterset_fields = ["document_type", "authenticity_assessment", "qa_status"]
    search_fields = ["document_id", "title", "author_or_speaker", "value_chain"]
    # DocumentRecord has no Meta.ordering -- an unordered queryset makes
    # PageNumberPagination's page boundaries arbitrary.
    queryset = DocumentRecord.objects.order_by("document_id")

    def perform_create(self, serializer):
        serializer.save(document_id=generate_document_id())


class DocumentRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [CanManageDocuments]
    serializer_class = DocumentRecordSerializer
    queryset = DocumentRecord.objects.all()


class DocumentAuthenticityView(APIView):
    """POST /api/v1/documents/{id}/authenticity/ -- always records a
    reviewer (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md)."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        assessment = request.data.get("assessment")
        if assessment not in AuthenticityAssessment.values:
            return Response({"error": {"code": "invalid_assessment", "message": "Invalid assessment.", "field_errors": {}}}, status=400)
        record_authenticity_assessment(document, assessment, reviewer=request.user)
        return Response(DocumentRecordSerializer(document).data)


class DocumentQAStatusView(APIView):
    """POST /api/v1/documents/{id}/qa-status/."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        qa_status = request.data.get("qa_status")
        if qa_status not in DocumentQAStatus.values:
            return Response({"error": {"code": "invalid_qa_status", "message": "Invalid qa_status.", "field_errors": {}}}, status=400)
        try:
            set_qa_status(document, qa_status, reviewer=request.user)
        except DocumentWorkflowError as exc:
            return Response({"error": {"code": "workflow_error", "message": str(exc), "field_errors": {}}}, status=400)
        return Response(DocumentRecordSerializer(document).data)
