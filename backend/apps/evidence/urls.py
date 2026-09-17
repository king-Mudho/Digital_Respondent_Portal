from django.urls import path

from .views import (
    DocumentAIDraftView,
    DocumentAISchemaView,
    DocumentAISubmitView,
    DocumentAuthenticityView,
    DocumentFileView,
    DocumentQAStatusView,
    DocumentRecordDetailView,
    DocumentRecordListCreateView,
)

app_name = "evidence"

urlpatterns = [
    path("documents/", DocumentRecordListCreateView.as_view(), name="list"),
    path("documents/ai-draft-schema/", DocumentAISchemaView.as_view(), name="ai-draft-schema"),
    path("documents/<int:pk>/", DocumentRecordDetailView.as_view(), name="detail"),
    path("documents/<int:pk>/authenticity/", DocumentAuthenticityView.as_view(), name="authenticity"),
    path("documents/<int:pk>/qa-status/", DocumentQAStatusView.as_view(), name="qa-status"),
    path("documents/<int:pk>/file/", DocumentFileView.as_view(), name="file"),
    path("documents/<int:pk>/ai-draft/", DocumentAIDraftView.as_view(), name="ai-draft"),
    path("documents/<int:pk>/ai-draft/submit/", DocumentAISubmitView.as_view(), name="ai-draft-submit"),
]
