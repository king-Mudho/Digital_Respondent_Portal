from django.urls import path

from .views import (
    AppointmentListCreateView,
    AppointmentStatusView,
    ContactEventListCreateView,
    EligibilityView,
)

app_name = "contacts"

urlpatterns = [
    path("eligibility/", EligibilityView.as_view(), name="eligibility"),
    path("contacts/<str:sample_id>/events/", ContactEventListCreateView.as_view(), name="contact-events"),
    path("appointments/", AppointmentListCreateView.as_view(), name="appointments"),
    path("appointments/<int:pk>/status/", AppointmentStatusView.as_view(), name="appointment-status"),
]
