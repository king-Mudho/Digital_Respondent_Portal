from django.urls import path

from .views import (
    ExpertConsentView,
    ExpertDetailView,
    ExpertInvitationEmailView,
    ExpertInvitationIssueView,
    ExpertInvitationRevokeView,
    ExpertKoboRedirectView,
    ExpertListView,
    ExpertValidateView,
)

app_name = "experts"

urlpatterns = [
    path("experts/", ExpertListView.as_view(), name="experts"),
    path("experts/<str:expert_id>/", ExpertDetailView.as_view(), name="expert"),
    path("expert-invitations/", ExpertInvitationIssueView.as_view(), name="invitations"),
    path("expert-invitations/validate/", ExpertValidateView.as_view(), name="validate"),
    path("expert-invitations/kobo-redirect-url/", ExpertKoboRedirectView.as_view(), name="kobo-redirect"),
    path("expert-invitations/<int:token_id>/send-email/", ExpertInvitationEmailView.as_view(), name="send-email"),
    path("expert-invitations/<int:token_id>/revoke/", ExpertInvitationRevokeView.as_view(), name="revoke"),
    path("expert-consent/", ExpertConsentView.as_view(), name="consent"),
]
