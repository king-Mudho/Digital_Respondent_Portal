from django.urls import path

from .exports import AnalysisExportView, OperationalExportView
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
    path("export/analysis/", AnalysisExportView.as_view(), name="export-analysis"),
    path("export/operational/", OperationalExportView.as_view(), name="export-operational"),
]
