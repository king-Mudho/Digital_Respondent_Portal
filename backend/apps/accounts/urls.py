from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AccessCheckView,
    ChangePasswordView,
    ContactRAListView,
    CurrentUserView,
    InternalTokenObtainView,
    QAAssigneeListView,
)

app_name = "accounts"

urlpatterns = [
    path("token/", InternalTokenObtainView.as_view(), name="token-obtain"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("can-open/", AccessCheckView.as_view(), name="can-open"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("contact-ras/", ContactRAListView.as_view(), name="contact-ras"),
    path("qa-assignees/", QAAssigneeListView.as_view(), name="qa-assignees"),
]
