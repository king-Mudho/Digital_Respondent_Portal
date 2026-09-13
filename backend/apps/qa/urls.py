from django.urls import path

from .views import (
    QAExceptionAssignView,
    QAExceptionQueueView,
    QAExceptionResolveView,
    QAQueueView,
    QASubmissionDecisionView,
)

app_name = "qa"

urlpatterns = [
    path("qa/queue/", QAQueueView.as_view(), name="queue"),
    path("qa/exceptions/", QAExceptionQueueView.as_view(), name="exceptions"),
    path("qa/exceptions/<int:pk>/assign/", QAExceptionAssignView.as_view(), name="exception-assign"),
    path("qa/exceptions/<int:pk>/resolve/", QAExceptionResolveView.as_view(), name="exception-resolve"),
    path("qa/submission/<int:pk>/decision/", QASubmissionDecisionView.as_view(), name="submission-decision"),
]
