from rest_framework import generics

from api.permissions import IsQAOrAdmin

from .models import KIIRecord
from .serializers import KIIRecordSerializer
from .services import generate_kii_id


class KIIRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/kii/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [IsQAOrAdmin]
    serializer_class = KIIRecordSerializer
    filterset_fields = ["status", "stakeholder_category", "transcript_status", "coding_status"]
    queryset = KIIRecord.objects.all()

    def perform_create(self, serializer):
        serializer.save(kii_id=generate_kii_id())


class KIIRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsQAOrAdmin]
    serializer_class = KIIRecordSerializer
    queryset = KIIRecord.objects.all()
