from rest_framework.generics import ListAPIView

from api.permissions import IsAdminOnly

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditLogView(ListAPIView):
    """GET /api/v1/audit/ -- internal, IsAdminOnly (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [IsAdminOnly]
    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.all()
    filterset_fields = ["action", "object_type"]
