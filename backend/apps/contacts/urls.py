from django.urls import path

from .finder_views import (
    ContactProposalAcceptView,
    ContactProposalRejectView,
    ContactReviewView,
    ContactSearchBatchView,
    ContactSearchView,
)
from .views import (
    AppointmentListCreateView,
    AppointmentStatusView,
    ContactEventListCreateView,
    EligibilityView,
    RespondentListCreateView,
    RespondentUpdateView,
)

app_name = "contacts"

urlpatterns = [
    path("eligibility/", EligibilityView.as_view(), name="eligibility"),
    path("contacts/respondents/<int:pk>/", RespondentUpdateView.as_view(), name="respondent-update"),
    # Fixed paths before the <sample_id> ones.
    path("contacts/contact-search/batch/", ContactSearchBatchView.as_view(), name="contact-search-batch"),
    path("contacts/contact-proposals/review/", ContactReviewView.as_view(), name="contact-proposal-review"),
    path("contacts/contact-proposals/<int:pk>/accept/", ContactProposalAcceptView.as_view(), name="contact-proposal-accept"),
    path("contacts/contact-proposals/<int:pk>/reject/", ContactProposalRejectView.as_view(), name="contact-proposal-reject"),
    path("contacts/<str:sample_id>/contact-search/", ContactSearchView.as_view(), name="contact-search"),
    path("contacts/<str:sample_id>/events/", ContactEventListCreateView.as_view(), name="contact-events"),
    path("contacts/<str:sample_id>/respondents/", RespondentListCreateView.as_view(), name="respondents"),
    path("appointments/", AppointmentListCreateView.as_view(), name="appointments"),
    path("appointments/<int:pk>/status/", AppointmentStatusView.as_view(), name="appointment-status"),
]
