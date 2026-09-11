from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Mounted at "django-admin/", not Django's conventional "admin/" -- the
    # frontend's Research Operations Centre already owns "/admin" (see
    # frontend/app/admin/, docs/07_FRONTEND_ARCHITECTURE.md), and both apps
    # share one production origin behind a single nginx proxy
    # (docs/23_DEPLOYMENT_ARCHITECTURE.md). Mirrors the sibling ABI project's
    # identical fix -- see its docs/PRODUCTION_ARCHITECTURE.md for the full
    # story of why this must be done in urls.py, not as an nginx rewrite.
    path("django-admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("api/v1/", include("api.urls")),
]
