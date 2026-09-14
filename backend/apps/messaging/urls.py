from django.urls import path

from .views import FollowUpListView, FollowUpMarkSentView

app_name = "messaging"

urlpatterns = [
    path("follow-ups/", FollowUpListView.as_view(), name="follow-ups"),
    path("follow-ups/mark-sent/", FollowUpMarkSentView.as_view(), name="follow-ups-mark-sent"),
]
