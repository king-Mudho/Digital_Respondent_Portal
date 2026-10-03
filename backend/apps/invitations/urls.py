from django.urls import path

from .batch_views import (
    InvitationBatchDetailView,
    InvitationBatchView,
    WhatsAppPrepareView,
    WhatsAppQueueView,
)
from .views import InvitationEmailView, InvitationIssueView, InvitationRevokeView, InvitationValidateView

app_name = "invitations"

urlpatterns = [
    path("invitations/validate/", InvitationValidateView.as_view(), name="validate"),
    path("invitations/", InvitationIssueView.as_view(), name="issue"),
    path("invitations/batch/", InvitationBatchView.as_view(), name="batch"),
    path("invitations/batch/<int:pk>/", InvitationBatchDetailView.as_view(), name="batch-detail"),
    path("invitations/whatsapp-queue/", WhatsAppQueueView.as_view(), name="whatsapp-queue"),
    path("invitations/whatsapp-queue/<str:sample_id>/prepare/", WhatsAppPrepareView.as_view(), name="whatsapp-prepare"),
    path("invitations/<int:token_id>/revoke/", InvitationRevokeView.as_view(), name="revoke"),
    path("invitations/<int:token_id>/send-email/", InvitationEmailView.as_view(), name="send-email"),
]
