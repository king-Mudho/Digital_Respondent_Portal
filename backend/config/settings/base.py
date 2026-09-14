"""
Base Django settings for the ABF-FST Digital Respondent Portal backend.

This portal never computes, stores, or displays an ABI score -- see
docs/25_FUTURE_ABI_ENGINE_PHASE4.md and AGENTS.md ground rule 3. Its own
"methodology" (identifier scheme, workflow status machine, QA thresholds) is
config/data-driven per AGENTS.md ground rule 7, never hardcoded here.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

APP_DOMAIN = env("APP_DOMAIN", default="research.agribizframework.com")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "apps.accounts",
    "apps.sampling",
    "apps.contacts",
    "apps.consent",
    "apps.invitations",
    "apps.kobo",
    "apps.messaging",
    "apps.kii",
    "apps.evidence",
    "apps.qa",
    "apps.dashboards",
    "apps.costs",
    "apps.audit",
    "apps.proit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Separate database instance from the sibling ABI project's abi_db -- see
# docs/03_SYSTEM_ARCHITECTURE.md and docs/20_EMBEDDING_WITH_ABI.md.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://drp_user:devpassword@localhost:5432/drp_dev",
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Harare"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Internal endpoints require an internal Role via explicit permission
    # classes (api/permissions.py); public respondent endpoints use AllowAny
    # but scope every query to the single SampleCase resolved from the
    # invitation token -- see docs/06_API_ARCHITECTURE.md and
    # docs/08_BACKEND_ARCHITECTURE.md "Permissions".
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # SearchFilter backs the ?search= box on the register screens. The
    # registers hold 400 Main + 400 Reserve cases, 90 KII records and 100
    # documents against a page size of 20 -- paging to find one row is not
    # a workable field workflow.
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "api.throttling.PerTokenThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Public token-validation/eligibility/consent endpoints -- blunts
        # token-guessing/enumeration per docs/10_INVITATION_AND_CONSENT.md.
        "anon": "30/minute",
        "invitation_token": "20/minute",
        # Internal sign-in, on its own bucket rather than sharing "anon"
        # with the respondent endpoints (api/throttling.LoginRateThrottle).
        # Still tight enough to blunt password guessing, but a whole
        # research team behind one office IP no longer competes with
        # respondent traffic for the same allowance. Configurable so the
        # rate can be tightened in production without a code change.
        "login": env("LOGIN_THROTTLE_RATE", default="30/minute"),
        # Public respondent journey, per IP (api/throttling.RespondentRateThrottle).
        # Higher than `anon` because respondents on mobile networks share
        # carrier-grade NAT addresses; the per-token limit above still applies.
        "respondent": env("RESPONDENT_THROTTLE_RATE", default="120/minute"),
    },
    "EXCEPTION_HANDLER": "api.exceptions.drp_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ABF-FST Digital Respondent Portal API",
    "DESCRIPTION": (
        "Research-operations platform API for the ABF-FST study. Not a "
        "questionnaire engine (KoboToolbox) and not a bankability-scoring "
        "tool (see docs/25_FUTURE_ABI_ENGINE_PHASE4.md)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=30)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"]
)

# --- Invitation tokens (docs/10_INVITATION_AND_CONSENT.md) -----------------
# Config-driven, not hardcoded, so the PI can tune without a redeploy
# (AGENTS.md ground rule 7).
INVITATION_TOKEN_BYTES = env.int("INVITATION_TOKEN_BYTES", default=32)
INVITATION_TOKEN_EXPIRY_DAYS = env.int("INVITATION_TOKEN_EXPIRY_DAYS", default=14)

# --- PROIT (docs: ABF-FST_PROIT_v1.0_Portal_Deployment_Tool) ---------------
# The tool's own status line is "DEPLOYMENT-READY CONTROLLED ADD-ON --
# subject to supervisor/ethics change-control decision", and its
# recommended deployment sequence puts an "Ethics/change-control review"
# step before any soft launch or real respondent use. This flag is the
# actual enforcement of that gate, not just a comment: researchers can
# build and lock pre-profiles against real or synthetic cases regardless,
# but the respondent-facing verification screen never renders -- the
# respondent flow behaves exactly as it did before PROIT existed -- until
# this is explicitly turned on post-approval.
PROIT_ENABLED_FOR_RESPONDENTS = env.bool("PROIT_ENABLED_FOR_RESPONDENTS", default=False)

# --- KoboToolbox integration (docs/11_KOBOTOOLBOX_INTEGRATION.md) ----------
KOBO_API_BASE_URL = env("KOBO_API_BASE_URL", default="https://kf.kobotoolbox.org")
KOBO_API_TOKEN = env("KOBO_API_TOKEN", default="")
KOBO_ASSET_UID = env("KOBO_ASSET_UID", default="")
# The deployed form's public web link, exactly as KoboToolbox shows it on the
# project's "Collect data" page, e.g. https://ee.kobotoolbox.org/x/AbCd1234.
# NOT derivable from KOBO_ASSET_UID: web forms are served by the Enketo host
# (ee.) under their own short form ID, while the asset UID is the 22-character
# project ID used only by the API on kf. Until 2026-09-14 the link was built
# as kf.kobotoolbox.org/x/<asset_uid>, which would have 404'd for every
# respondent even with a correct asset UID configured.
KOBO_FORM_URL = env("KOBO_FORM_URL", default="")
KOBO_WEBHOOK_SHARED_SECRET = env("KOBO_WEBHOOK_SHARED_SECRET", default="")
KOBO_RECONCILIATION_INTERVAL_MINUTES = env.int(
    "KOBO_RECONCILIATION_INTERVAL_MINUTES", default=15
)

# --- WhatsApp Business Platform (docs/12_CONTACT_CRM_AND_MESSAGING.md) -----
WHATSAPP_API_BASE_URL = env("WHATSAPP_API_BASE_URL", default="")
WHATSAPP_API_TOKEN = env("WHATSAPP_API_TOKEN", default="")
WHATSAPP_BUSINESS_ACCOUNT_ID = env("WHATSAPP_BUSINESS_ACCOUNT_ID", default="")

# --- Celery (reconciliation + reminder queue only -- docs/04_TECH_STACK.md) -
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --- Backups (docs/23_DEPLOYMENT_ARCHITECTURE.md RPO/RTO targets) ----------
BACKUP_RPO_HOURS = env.int("BACKUP_RPO_HOURS", default=4)
BACKUP_RTO_HOURS = env.int("BACKUP_RTO_HOURS", default=4)
