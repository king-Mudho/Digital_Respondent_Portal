from django.urls import path

from .views import (
    KIICodingStatusView,
    KIIConsentSubmitView,
    KIIConsentView,
    KIIInvitationEmailView,
    KIIInvitationIssueView,
    KIIInvitationRevokeView,
    KIIInvitationTextView,
    KIIInvitationValidateView,
    KIIKoboRedirectView,
    KIIRecordDetailView,
    KIIRecordListCreateView,
    KIIStatusTransitionView,
    KIITranscriptStatusView,
)

app_name = "kii"

urlpatterns = [
    path("kii/", KIIRecordListCreateView.as_view(), name="list"),
    path("kii/<int:pk>/", KIIRecordDetailView.as_view(), name="detail"),
    path("kii/<int:pk>/status/", KIIStatusTransitionView.as_view(), name="status"),
    path("kii/<int:pk>/consent/", KIIConsentView.as_view(), name="consent"),
    path("kii/<int:pk>/transcript-status/", KIITranscriptStatusView.as_view(), name="transcript-status"),
    path("kii/<int:pk>/coding-status/", KIICodingStatusView.as_view(), name="coding-status"),
    # KII self-service invitation (2026-10-01) -- public respondent-facing
    # surface under kii-invitations/, parallel to apps.invitations.urls'
    # invitations/ (see apps/kii/services.py for why it's a separate model
    # and token lifecycle rather than reusing InvitationToken).
    path("kii-invitations/", KIIInvitationIssueView.as_view(), name="invitation-issue"),
    path("kii-invitations/validate/", KIIInvitationValidateView.as_view(), name="invitation-validate"),
    path("kii-invitations/<int:token_id>/revoke/", KIIInvitationRevokeView.as_view(), name="invitation-revoke"),
    path("kii-invitations/<int:token_id>/send-email/", KIIInvitationEmailView.as_view(), name="invitation-send-email"),
    path("kii-invitations/<int:token_id>/send-sms/", KIIInvitationTextView.as_view(channel="SMS"), name="invitation-send-sms"),
    path("kii-invitations/<int:token_id>/send-whatsapp/", KIIInvitationTextView.as_view(channel="WHATSAPP"), name="invitation-send-whatsapp"),
    path("kii-invitations/kobo-redirect-url/", KIIKoboRedirectView.as_view(), name="invitation-kobo-redirect-url"),
    path("kii-consent/", KIIConsentSubmitView.as_view(), name="kii-consent-submit"),
]
