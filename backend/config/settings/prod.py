from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Nginx terminates TLS and proxies to Gunicorn over plain HTTP on localhost.
# Without this, Django never sees a request as secure (no X-Forwarded-Proto
# awareness), so SECURE_SSL_REDIRECT above would redirect every request in
# an infinite loop -- same lesson as the sibling ABI project's prod.py.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Required by Django's CSRF origin check for POSTs (e.g. Django admin login)
# arriving over HTTPS through the reverse proxy; must include the scheme.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if not env("DJANGO_SECRET_KEY", default=None):
    raise RuntimeError("DJANGO_SECRET_KEY must be set via environment in production")
