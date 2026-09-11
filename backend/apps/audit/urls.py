from django.urls import path

from .views import AuditLogView

app_name = "audit"

urlpatterns = [
    path("audit/", AuditLogView.as_view(), name="audit-log"),
]
