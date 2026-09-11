from rest_framework import generics

from api.permissions import IsFieldCoordinatorOrAdmin

from .models import CostEvent
from .serializers import CostEventSerializer


class CostEventListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = CostEventSerializer
    queryset = CostEvent.objects.all()

    def perform_create(self, serializer):
        serializer.save(approved_by=self.request.user)
