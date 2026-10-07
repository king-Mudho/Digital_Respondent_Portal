from django.urls import path

from .views import (
    CaseOutreachView,
    ConversationHandledView,
    ConversationListView,
    ConversationReplyView,
    FollowUpListView,
    FollowUpMarkSentView,
    TwilioInboundView,
    TwilioStatusView,
)

app_name = "messaging"

urlpatterns = [
    path("follow-ups/", FollowUpListView.as_view(), name="follow-ups"),
    path("follow-ups/mark-sent/", FollowUpMarkSentView.as_view(), name="follow-ups-mark-sent"),
    path("twilio/status/", TwilioStatusView.as_view(), name="twilio-status"),
    path("twilio/inbound/", TwilioInboundView.as_view(), name="twilio-inbound"),
    path("conversations/", ConversationListView.as_view(), name="conversations"),
    path("conversations/<int:pk>/handled/", ConversationHandledView.as_view(), name="conversation-handled"),
    path("conversations/<int:pk>/reply/", ConversationReplyView.as_view(), name="conversation-reply"),
    path("outreach/", CaseOutreachView.as_view(), name="outreach"),
]
