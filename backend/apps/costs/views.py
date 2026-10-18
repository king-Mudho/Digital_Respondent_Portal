from django.db.models import Sum
from rest_framework import generics
from rest_framework.response import Response

from api.permissions import IsFieldCoordinatorOrAdmin
from apps.audit.utils import log_action

from .models import CostEvent
from .serializers import CostEventSerializer

FIELDS = ("date", "category", "description", "paid_to", "amount", "currency")


def _snapshot(cost: CostEvent) -> dict:
    return {f: str(getattr(cost, f)) for f in FIELDS}


class CostEventListCreateView(generics.ListCreateAPIView):
    """GET /api/v1/costs/?month=YYYY-MM&category=... -- every cost entry, newest first, with the total of what is
    listed (PI, 18 Oct 2026: a table of each cost with its date, what it was for and who was paid). Not paginated:
    a study's cost entries number in the hundreds at most, and the total must cover all of them.
    POST -- record one cost; it must say what it was for."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = CostEventSerializer
    pagination_class = None

    def get_queryset(self):
        qs = CostEvent.objects.select_related("approved_by").order_by("-date", "-created_at")
        month = (self.request.query_params.get("month") or "").strip()
        if len(month) == 7 and month[4] == "-" and month.replace("-", "").isdigit():
            qs = qs.filter(date__year=int(month[:4]), date__month=int(month[5:]))
        category = (self.request.query_params.get("category") or "").strip()
        if category:
            qs = qs.filter(category=category)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        total = qs.aggregate(total=Sum("amount"))["total"] or 0
        return Response({"results": self.get_serializer(qs, many=True).data, "count": qs.count(), "total": str(total)})

    def perform_create(self, serializer):
        cost = serializer.save(approved_by=self.request.user)
        log_action("cost.recorded", cost, {**_snapshot(cost), "user_id": self.request.user.id}, user=self.request.user)


class CostEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """PATCH -- correct an entry; DELETE -- remove one recorded by mistake. Both audited with what it was before."""

    permission_classes = [IsFieldCoordinatorOrAdmin]
    serializer_class = CostEventSerializer
    queryset = CostEvent.objects.select_related("approved_by")

    def perform_update(self, serializer):
        before = _snapshot(serializer.instance)
        cost = serializer.save()
        after = _snapshot(cost)
        changed = {f: {"from": before[f], "to": after[f]} for f in FIELDS if before[f] != after[f]}
        log_action("cost.updated", cost, {"changed": changed, "user_id": self.request.user.id}, user=self.request.user)

    def perform_destroy(self, instance):
        log_action("cost.deleted", instance, {**_snapshot(instance), "user_id": self.request.user.id}, user=self.request.user)
        instance.delete()
