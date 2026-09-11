from rest_framework import generics

from api.permissions import IsQAOrAdmin

from .models import DocumentRecord
from .serializers import DocumentRecordSerializer
from .services import generate_document_id


class DocumentRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/documents/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [IsQAOrAdmin]
    serializer_class = DocumentRecordSerializer
    filterset_fields = ["document_type", "authenticity_assessment", "qa_status"]
    queryset = DocumentRecord.objects.all()

    def perform_create(self, serializer):
        serializer.save(document_id=generate_document_id())


class DocumentRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsQAOrAdmin]
    serializer_class = DocumentRecordSerializer
    queryset = DocumentRecord.objects.all()
