from django.urls import path

from .views import ConsentSubmitView

app_name = "consent"

urlpatterns = [
    path("consent/", ConsentSubmitView.as_view(), name="submit"),
]
