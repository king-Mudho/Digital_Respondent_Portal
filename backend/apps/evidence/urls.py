from django.urls import path

from .views import (
    DocumentAuthenticityView,
    DocumentQAStatusView,
    DocumentRecordDetailView,
    DocumentRecordListCreateView,
)

app_name = "evidence"

urlpatterns = [
    path("documents/", DocumentRecordListCreateView.as_view(), name="list"),
    path("documents/<int:pk>/", DocumentRecordDetailView.as_view(), name="detail"),
    path("documents/<int:pk>/authenticity/", DocumentAuthenticityView.as_view(), name="authenticity"),
    path("documents/<int:pk>/qa-status/", DocumentQAStatusView.as_view(), name="qa-status"),
]
