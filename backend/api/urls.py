from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.sampling.urls")),
    path("", include("apps.invitations.urls")),
    path("", include("apps.consent.urls")),
    path("", include("apps.contacts.urls")),
    path("", include("apps.messaging.urls")),
    path("", include("apps.kobo.urls")),
    path("", include("apps.kii.urls")),
    path("", include("apps.evidence.urls")),
    path("", include("apps.qa.urls")),
    path("", include("apps.dashboards.urls")),
    path("", include("apps.costs.urls")),
    path("", include("apps.audit.urls")),
    path("proit/", include("apps.proit.urls")),
]
