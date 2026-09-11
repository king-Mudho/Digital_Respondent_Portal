from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ALLOW_ALL_ORIGINS = True

# Celery tasks run synchronously in dev by default so a local Redis broker
# isn't required just to exercise reconciliation/reminder logic manually;
# override via CELERY_TASK_ALWAYS_EAGER=False in .env once Redis is running.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)  # noqa: F405
