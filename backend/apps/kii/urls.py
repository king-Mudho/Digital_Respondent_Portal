from django.urls import path

from .views import KIIRecordDetailView, KIIRecordListCreateView

app_name = "kii"

urlpatterns = [
    path("kii/", KIIRecordListCreateView.as_view(), name="list"),
    path("kii/<int:pk>/", KIIRecordDetailView.as_view(), name="detail"),
]
