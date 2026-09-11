from django.urls import path

from .views import InvitationIssueView, InvitationRevokeView, InvitationValidateView

app_name = "invitations"

urlpatterns = [
    path("invitations/validate/", InvitationValidateView.as_view(), name="validate"),
    path("invitations/", InvitationIssueView.as_view(), name="issue"),
    path("invitations/<int:token_id>/revoke/", InvitationRevokeView.as_view(), name="revoke"),
]
