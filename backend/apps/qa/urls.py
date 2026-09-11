from django.urls import path

from .views import QAQueueView, QASubmissionDecisionView

app_name = "qa"

urlpatterns = [
    path("qa/queue/", QAQueueView.as_view(), name="queue"),
    path("qa/submission/<int:pk>/decision/", QASubmissionDecisionView.as_view(), name="submission-decision"),
]
