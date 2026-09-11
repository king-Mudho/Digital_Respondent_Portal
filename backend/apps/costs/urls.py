from django.urls import path

from .views import CostEventListCreateView

app_name = "costs"

urlpatterns = [
    path("costs/", CostEventListCreateView.as_view(), name="costs"),
]
