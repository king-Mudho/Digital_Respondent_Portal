from django.urls import path

from .views import (
    ContactDashboardView,
    CostDashboardView,
    ExecutiveDashboardView,
    KIIDocumentDashboardView,
    QADashboardView,
    SamplingDashboardView,
)

app_name = "dashboards"

urlpatterns = [
    path("dashboards/executive/", ExecutiveDashboardView.as_view(), name="executive"),
    path("dashboards/sampling/", SamplingDashboardView.as_view(), name="sampling"),
    path("dashboards/contact/", ContactDashboardView.as_view(), name="contact"),
    path("dashboards/qa/", QADashboardView.as_view(), name="qa"),
    path("dashboards/kii-documents/", KIIDocumentDashboardView.as_view(), name="kii-documents"),
    path("dashboards/cost/", CostDashboardView.as_view(), name="cost"),
]
