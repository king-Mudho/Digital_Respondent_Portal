# 24 — Environment configuration

The domain is planned as `research.agribizframework.com`, but must still be read from
environment configuration everywhere — never hardcoded in source — matching
`AGENTS.md` ground rule 9 and the ABI project's own equivalent rule.

## `backend/.env.example`

```
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=changeme
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=research.agribizframework.com

DATABASE_URL=postgres://drp_user:changeme@localhost:5432/drp_db

JWT_SIGNING_KEY=changeme
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=30
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

INVITATION_TOKEN_BYTES=32
INVITATION_TOKEN_EXPIRY_DAYS=14

KOBO_API_BASE_URL=https://kf.kobotoolbox.org
KOBO_API_TOKEN=changeme
KOBO_ASSET_UID=changeme
KOBO_WEBHOOK_SHARED_SECRET=changeme
KOBO_RECONCILIATION_INTERVAL_MINUTES=15

WHATSAPP_API_BASE_URL=changeme
WHATSAPP_API_TOKEN=changeme
WHATSAPP_BUSINESS_ACCOUNT_ID=changeme

CELERY_BROKER_URL=redis://localhost:6379/0

CORS_ALLOWED_ORIGINS=https://research.agribizframework.com
CSRF_TRUSTED_ORIGINS=https://research.agribizframework.com

BACKUP_RPO_HOURS=4
BACKUP_RTO_HOURS=4
```

`CSRF_TRUSTED_ORIGINS` (with scheme) is required for the Django admin login behind the
reverse proxy, exactly as in the ABI project's own `.env.example` — `SECURE_PROXY_SSL_
HEADER` must be set in `config/settings/prod.py` so Django recognises HTTPS requests
forwarded by Nginx.

## `frontend/.env.example`

```
NEXT_PUBLIC_APP_DOMAIN=research.agribizframework.com
NEXT_PUBLIC_API_BASE_URL=https://research.agribizframework.com/api/v1
NEXT_PUBLIC_APP_ENV=production
```

## Local development overrides

```
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://drp_user:devpassword@localhost:5432/drp_dev
KOBO_ASSET_UID=<dedicated test/staging asset, never the production asset>
CORS_ALLOWED_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_ENV=development
```

## Rules

- Never commit a real `.env` file — only `.env.example` files are checked in.
- Every secret (Django secret key, JWT signing key, DB password, Kobo API token,
  WhatsApp API token) comes from the environment, never a literal in `settings/*.py` or
  frontend config files.
- The frontend builds its API base URL from `NEXT_PUBLIC_API_BASE_URL`, never a
  hardcoded domain string inside components.
- `KOBO_ASSET_UID` in dev/staging must point at the dedicated test asset
  (`11_KOBOTOOLBOX_INTEGRATION.md`) — a code review should treat a dev environment
  pointed at the production Kobo asset as a blocking defect.
