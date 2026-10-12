from django.urls import path

from .views import (
    CaseOutreachView,
    CommunicationHandledView,
    CommunicationSendView,
    CommunicationSummaryView,
    CommunicationThreadListView,
    CommunicationThreadView,
    CommunicationUnknownView,
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
    path("communications/summary/", CommunicationSummaryView.as_view(), name="communications-summary"),
    path("communications/threads/", CommunicationThreadListView.as_view(), name="communications-threads"),
    path("communications/threads/<str:kind>/<int:pk>/", CommunicationThreadView.as_view(), name="communications-thread"),
    path("communications/threads/<str:kind>/<int:pk>/send/", CommunicationSendView.as_view(), name="communications-send"),
    path("communications/threads/<str:kind>/<int:pk>/handled/", CommunicationHandledView.as_view(), name="communications-handled"),
    path("communications/unknown/", CommunicationUnknownView.as_view(), name="communications-unknown"),
]
