from django.urls import path

from .views import KoboReconcileView, KoboRedirectURLView, KoboWebhookView

app_name = "kobo"

urlpatterns = [
    path("kobo/redirect-url/", KoboRedirectURLView.as_view(), name="redirect-url"),
    path("kobo/webhook/", KoboWebhookView.as_view(), name="webhook"),
    path("kobo/reconcile/", KoboReconcileView.as_view(), name="reconcile"),
]
