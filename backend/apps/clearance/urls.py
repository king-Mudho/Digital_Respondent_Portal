from django.urls import path

from .views import (
    ClearanceDocumentDetailView,
    ClearanceDocumentFileView,
    ClearanceDocumentListCreateView,
    RespondentClearanceDocumentFileView,
    RespondentClearanceDocumentsView,
)

app_name = "clearance"

urlpatterns = [
    path("clearance-documents/", ClearanceDocumentListCreateView.as_view(), name="list-create"),
    path("clearance-documents/<int:pk>/", ClearanceDocumentDetailView.as_view(), name="detail"),
    path("clearance-documents/<int:pk>/file/", ClearanceDocumentFileView.as_view(), name="file"),
    path("respondent-clearance-documents/", RespondentClearanceDocumentsView.as_view(), name="respondent-list"),
    path("respondent-clearance-documents/<int:pk>/file/", RespondentClearanceDocumentFileView.as_view(), name="respondent-file"),
]
