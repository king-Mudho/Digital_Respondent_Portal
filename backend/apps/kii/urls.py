from django.urls import path

from .views import (
    KIICodingStatusView,
    KIIConsentView,
    KIIRecordDetailView,
    KIIRecordListCreateView,
    KIIStatusTransitionView,
    KIITranscriptStatusView,
)

app_name = "kii"

urlpatterns = [
    path("kii/", KIIRecordListCreateView.as_view(), name="list"),
    path("kii/<int:pk>/", KIIRecordDetailView.as_view(), name="detail"),
    path("kii/<int:pk>/status/", KIIStatusTransitionView.as_view(), name="status"),
    path("kii/<int:pk>/consent/", KIIConsentView.as_view(), name="consent"),
    path("kii/<int:pk>/transcript-status/", KIITranscriptStatusView.as_view(), name="transcript-status"),
    path("kii/<int:pk>/coding-status/", KIICodingStatusView.as_view(), name="coding-status"),
]
