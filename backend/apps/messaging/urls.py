from django.urls import path

from .views import FollowUpListView, FollowUpMarkSentView, TwilioStatusView

app_name = "messaging"

urlpatterns = [
    path("follow-ups/", FollowUpListView.as_view(), name="follow-ups"),
    path("follow-ups/mark-sent/", FollowUpMarkSentView.as_view(), name="follow-ups-mark-sent"),
    path("twilio/status/", TwilioStatusView.as_view(), name="twilio-status"),
]
