from django.urls import path

from .views import (
    EvidenceSourceListCreateView,
    FieldCatalogView,
    PreProfileDetailView,
    PreProfileFieldListCreateView,
    PreProfileListCreateView,
    PreProfileLockView,
    ProbeTemplateView,
    RespondentPreProfileView,
    RespondentVerifyView,
)

urlpatterns = [
    path("field-catalog/", FieldCatalogView.as_view(), name="field-catalog"),
    path("probe-templates/", ProbeTemplateView.as_view(), name="probe-templates"),
    path("pre-profiles/", PreProfileListCreateView.as_view(), name="pre-profile-list"),
    path("pre-profiles/<int:pk>/", PreProfileDetailView.as_view(), name="pre-profile-detail"),
    path("pre-profiles/<int:pk>/lock/", PreProfileLockView.as_view(), name="pre-profile-lock"),
    path("pre-profiles/<int:pre_profile_id>/fields/", PreProfileFieldListCreateView.as_view(), name="pre-profile-fields"),
    path("fields/<int:field_id>/evidence/", EvidenceSourceListCreateView.as_view(), name="field-evidence"),
    path("respondent-profile/", RespondentPreProfileView.as_view(), name="respondent-profile"),
    path("respondent-verify/", RespondentVerifyView.as_view(), name="respondent-verify"),
]
