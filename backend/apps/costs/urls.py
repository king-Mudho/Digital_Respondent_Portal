from django.urls import path

from .views import CostEventDetailView, CostEventListCreateView

app_name = "costs"

urlpatterns = [
    path("costs/", CostEventListCreateView.as_view(), name="costs"),
    path("costs/<int:pk>/", CostEventDetailView.as_view(), name="cost-detail"),
]
