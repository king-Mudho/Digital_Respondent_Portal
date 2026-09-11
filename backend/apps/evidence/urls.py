from django.urls import path

from .views import DocumentRecordDetailView, DocumentRecordListCreateView

app_name = "evidence"

urlpatterns = [
    path("documents/", DocumentRecordListCreateView.as_view(), name="list"),
    path("documents/<int:pk>/", DocumentRecordDetailView.as_view(), name="detail"),
]
