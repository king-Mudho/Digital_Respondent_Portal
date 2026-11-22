from django.urls import path

from .exports import AnalysisExportView, OperationalExportView, OutreachExportView
from .views import (
    ContactDashboardView,
    CostDashboardView,
    ExecutiveDashboardView,
    KIIDocumentDashboardView,
    QADashboardView,
    ReportsOverviewView,
    SamplingDashboardView,
    TwilioBalanceView,
)

app_name = "dashboards"

urlpatterns = [
    path("dashboards/executive/", ExecutiveDashboardView.as_view(), name="executive"),
    path("dashboards/sampling/", SamplingDashboardView.as_view(), name="sampling"),
    path("dashboards/contact/", ContactDashboardView.as_view(), name="contact"),
    path("dashboards/qa/", QADashboardView.as_view(), name="qa"),
    path("dashboards/kii-documents/", KIIDocumentDashboardView.as_view(), name="kii-documents"),
    path("dashboards/cost/", CostDashboardView.as_view(), name="cost"),
    path("dashboards/twilio-balance/", TwilioBalanceView.as_view(), name="twilio-balance"),
    path("reports/overview/", ReportsOverviewView.as_view(), name="reports-overview"),
    path("export/analysis/", AnalysisExportView.as_view(), name="export-analysis"),
    path("export/operational/", OperationalExportView.as_view(), name="export-operational"),
    path("export/outreach/", OutreachExportView.as_view(), name="export-outreach"),
]
