from django.urls import path

from .views import (
    OrganisationListCreateView,
    ReserveActivateView,
    SampleCaseDetailView,
    SampleCaseListCreateView,
    WorkflowTransitionView,
)

app_name = "sampling"

urlpatterns = [
    path("organisations/", OrganisationListCreateView.as_view(), name="organisations"),
    path("sample-cases/", SampleCaseListCreateView.as_view(), name="list"),
    path("sample-cases/<str:sample_id>/", SampleCaseDetailView.as_view(), name="detail"),
    path("sample-cases/<str:sample_id>/activate-reserve/", ReserveActivateView.as_view(), name="activate-reserve"),
    path("sample-cases/<str:sample_id>/transition/", WorkflowTransitionView.as_view(), name="transition"),
]
