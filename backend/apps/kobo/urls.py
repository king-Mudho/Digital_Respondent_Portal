from django.urls import path

from .copy_views import KoboFormSubmissionsView, KoboFormsView, KoboSubmissionEmailView, KoboSubmissionPDFView
from .views import (
    KoboReconcileView,
    KoboReconciliationStatusView,
    KoboRedirectURLView,
    KoboWebhookView,
)

app_name = "kobo"

urlpatterns = [
    path("kobo/redirect-url/", KoboRedirectURLView.as_view(), name="redirect-url"),
    path("kobo/webhook/", KoboWebhookView.as_view(), name="webhook"),
    path("kobo/reconcile/", KoboReconcileView.as_view(), name="reconcile"),
    path("kobo/reconciliation-status/", KoboReconciliationStatusView.as_view(), name="reconciliation-status"),
    path("kobo/forms/", KoboFormsView.as_view(), name="forms"),
    path("kobo/forms/<str:key>/submissions/", KoboFormSubmissionsView.as_view(), name="form-submissions"),
    path("kobo/forms/<str:key>/submissions/<int:submission_id>/pdf/", KoboSubmissionPDFView.as_view(), name="submission-pdf"),
    path("kobo/forms/<str:key>/submissions/<int:submission_id>/email/", KoboSubmissionEmailView.as_view(), name="submission-email"),
]
