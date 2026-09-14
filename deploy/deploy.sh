#!/usr/bin/env bash
#
# Build and (re)start the DRP application. Run for the first deploy and
# for every update afterwards.
#
#   sudo bash /srv/agribiz-drp/deploy/deploy.sh
#
# Mirrors the sibling ABI project's deploy.sh pattern (same VPS, same
# lessons -- see docs/PRODUCTION_ARCHITECTURE.md in that repo for "the
# 127.0.0.1 lesson" this script also respects), adapted for:
#   - a separate app user (agribiz-drp) and directory (/srv/agribiz-drp)
#   - separate loopback ports (8100/3100, vs. ABI's 8000/3000)
#   - two additional systemd units (Celery worker + Beat)
#   - a tighter memory budget (two full stacks now share ~956MB RAM --
#     docs/27_AGENT_EXECUTION_PLAN.md Phase 10 flagged this explicitly)

set -euo pipefail

APP_USER="agribiz-drp"
APP_DIR="/srv/agribiz-drp"
BACKEND="$APP_DIR/backend"
FRONTEND="$APP_DIR/frontend"
FRONTEND_RELEASES="$FRONTEND/releases"
FRONTEND_CURRENT="$FRONTEND/current"
PYTHON="python3.12"
KEEP_RELEASES=3

SITE_DOMAIN="${SITE_DOMAIN:-research.agribizframework.com}"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this with sudo."
[[ -d "$BACKEND"  ]] || die "$BACKEND not found. Copy the code to $APP_DIR first."
[[ -d "$FRONTEND" ]] || die "$FRONTEND not found. Copy the code to $APP_DIR first."
[[ -f "$BACKEND/.env"  ]] || die "$BACKEND/.env is missing (see deploy/env-templates/)."
[[ -f "$FRONTEND/.env" ]] || die "$FRONTEND/.env is missing (see deploy/env-templates/)."

APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
as_app() { sudo -u "$APP_USER" env "HOME=${APP_HOME:-/srv/agribiz-drp}" "PATH=$PATH" "$@"; }
as_app_django() {
    sudo -u "$APP_USER" env "HOME=${APP_HOME:-/srv/agribiz-drp}" "PATH=$PATH" \
        "DJANGO_SETTINGS_MODULE=config.settings.prod" "$@"
}

log "Fixing ownership"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Memory headroom check -- this box now runs ABI's stack alongside DRP's;
# warn (don't block) if things look tight before the memory-hungry
# frontend build step.
AVAILABLE_MB="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
if (( AVAILABLE_MB < 150 )); then
    warn "Only ${AVAILABLE_MB}MB memory available. The frontend build may be slow or OOM."
    warn "Consider stopping non-essential services temporarily, or building at a quiet time."
fi

# ------------------------------------------------------------------ backup

# Tested with -f and invoked through `bash`, not tested with -x: the
# executable bit does not survive every code-transfer route (git archive
# into a tarball, cp -a from a checkout made on Windows), and when it was
# tested with -x this whole block silently became a one-line warning that
# scrolled past in the deploy output. Four consecutive deploys ran with no
# backup taken, and the only restore point for the imported registers
# predated the import (found 2026-09-13).
if [[ "${SKIP_BACKUP:-0}" == "1" ]]; then
    warn "SKIP_BACKUP=1 -- deploying with NO restore point, at your own risk."
elif [[ ! -f "$APP_DIR/deploy/backup.sh" ]]; then
    die "deploy/backup.sh is missing. Refusing to migrate without a restore point."
elif ! systemctl is-active --quiet postgresql; then
    warn "PostgreSQL is not active -- skipping backup. Expected only on a first deploy."
else
    log "Backing up the database before migrating"
    if bash "$APP_DIR/deploy/backup.sh"; then
        chown -R "$APP_USER:$APP_USER" "$APP_DIR/backups" 2>/dev/null || true
    else
        # A failed backup before a migration is not a warning. The whole
        # point of this step is to have something to roll back to.
        die "Backup FAILED. Refusing to migrate without a restore point. Fix the backup, or re-run with SKIP_BACKUP=1 if you accept the risk."
    fi
fi

# ------------------------------------------------------------------- backend

log "Installing Python dependencies"
if [[ ! -d "$BACKEND/venv" ]]; then
    as_app "$PYTHON" -m venv "$BACKEND/venv"
fi
as_app "$BACKEND/venv/bin/pip" install --quiet --upgrade pip
as_app "$BACKEND/venv/bin/pip" install --quiet -r "$BACKEND/requirements/prod.txt"

as_app mkdir -p "$BACKEND/media" "$APP_DIR/logs"

log "Checking Django configuration"
( cd "$BACKEND" && as_app_django "$BACKEND/venv/bin/python" manage.py check --deploy ) || \
    die "Django checks failed -- fix backend/.env before continuing."

log "Running database migrations"
( cd "$BACKEND" && as_app_django "$BACKEND/venv/bin/python" manage.py migrate --noinput )

log "Collecting Django static files"
as_app mkdir -p "$BACKEND/staticfiles"
( cd "$BACKEND" && as_app_django "$BACKEND/venv/bin/python" manage.py collectstatic --noinput --clear )

# ------------------------------------------------------------------ frontend

log "Checking Node version"
NODE_MAJOR="$(node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || echo 0)"
if (( NODE_MAJOR < 20 )); then
    die "Node $(node --version 2>/dev/null || echo 'not installed') is too old. The frontend requires Node >= 20."
fi

log "Installing Node dependencies"
if ! ( cd "$FRONTEND" && as_app npm ci --no-audit --no-fund ); then
    warn "npm ci failed -- falling back to 'npm install'."
    ( cd "$FRONTEND" && as_app npm install --no-audit --no-fund )
fi

log "Building the frontend (this is the memory-hungry step)"
( cd "$FRONTEND" && as_app npm run build )

[[ -f "$FRONTEND/.next/standalone/server.js" ]] || \
    die "Build did not produce .next/standalone/server.js -- check next.config.ts has output: \"standalone\"."

log "Assembling frontend release"
RELEASE_ID="$(date +%Y%m%d%H%M%S)"
RELEASE_DIR="$FRONTEND_RELEASES/$RELEASE_ID"
mkdir -p "$RELEASE_DIR"

cp -r "$FRONTEND/.next/standalone/." "$RELEASE_DIR/"
mkdir -p "$RELEASE_DIR/.next"
cp -r "$FRONTEND/.next/static" "$RELEASE_DIR/.next/static"
[[ -d "$FRONTEND/public" ]] && cp -r "$FRONTEND/public" "$RELEASE_DIR/public"
cp "$FRONTEND/.env" "$RELEASE_DIR/.env"
chown -R "$APP_USER:$APP_USER" "$RELEASE_DIR"

ln -sfn "$RELEASE_DIR" "$FRONTEND_CURRENT"
chown -h "$APP_USER:$APP_USER" "$FRONTEND_CURRENT"

log "Pruning old releases (keeping last $KEEP_RELEASES)"
mapfile -t old_releases < <(ls -1 "$FRONTEND_RELEASES" 2>/dev/null | sort -r | tail -n +$((KEEP_RELEASES + 1)))
for old in "${old_releases[@]:-}"; do
    [[ -n "$old" ]] && rm -rf "${FRONTEND_RELEASES:?}/$old"
done

# --------------------------------------------------------------- services

log "Installing systemd units"
install -m 644 "$APP_DIR/systemd/drp-backend.service"       /etc/systemd/system/
install -m 644 "$APP_DIR/systemd/drp-frontend.service"      /etc/systemd/system/
install -m 644 "$APP_DIR/systemd/drp-celery-worker.service" /etc/systemd/system/
install -m 644 "$APP_DIR/systemd/drp-celery-beat.service"   /etc/systemd/system/
install -m 644 "$APP_DIR/systemd/drp-offsite-backup.service" /etc/systemd/system/
systemctl daemon-reload

log "Restarting services"
systemctl enable drp-backend drp-frontend drp-celery-worker drp-celery-beat >/dev/null 2>&1 || true
systemctl restart drp-backend
systemctl restart drp-frontend
systemctl restart drp-celery-worker
systemctl restart drp-celery-beat

# ------------------------------------------------------------------- nginx
#
# Same "let Certbot own the HTTPS block" rule as ABI's deploy.sh -- only
# install the base template on a first deploy; after certbot has run,
# validate what's live and leave it alone.

NGINX_CONF=/etc/nginx/conf.d/research.agribizframework.conf
if [[ -f "$NGINX_CONF" ]] && grep -q "managed by Certbot" "$NGINX_CONF"; then
    log "nginx config already certbot-managed -- validating in place, not overwriting"
    nginx -t || die "The currently installed nginx config is invalid."
else
    log "Installing nginx config (first deploy -- no certbot block yet)"
    install -m 644 "$APP_DIR/nginx/research.agribizframework.conf" "$NGINX_CONF"
    nginx -t || die "nginx config is invalid -- not reloading."
    systemctl reload nginx 2>/dev/null || systemctl start nginx
    warn "This is a fresh nginx config with no HTTPS block yet. Run certbot now:"
    warn "  certbot --nginx -d research.agribizframework.com --redirect"
fi

# ------------------------------------------------------------------- verify

log "Verifying"
sleep 4

check() {
    local name="$1" expected="$2"
    shift 2
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "$@" 2>/dev/null || echo 000)"
    if [[ "$code" == "$expected" ]]; then
        printf '    \033[1;32mok\033[0m   %-28s %s\n' "$name" "$code"
    else
        printf '    \033[1;31mFAIL\033[0m %-28s got %s, expected %s\n' "$name" "$code" "$expected"
        return 1
    fi
}

failed=0
check "backend (gunicorn)"  200 \
    -H "Host: $SITE_DOMAIN" -H "X-Forwarded-Proto: https" \
    "http://127.0.0.1:8100/api/schema/" || failed=1
check "frontend (node ssr)" 200 "http://127.0.0.1:3100/" || failed=1

if systemctl is-active --quiet nginx; then
    if curl -sSk --resolve "$SITE_DOMAIN:443:127.0.0.1" -o /dev/null \
            --max-time 10 "https://$SITE_DOMAIN/" 2>/dev/null; then
        check "through nginx (https)" 200 \
            -k --resolve "$SITE_DOMAIN:443:127.0.0.1" "https://$SITE_DOMAIN/" || failed=1
    else
        check "through nginx (http)" 200 \
            -H "Host: $SITE_DOMAIN" "http://127.0.0.1/" || failed=1
    fi
else
    printf '    \033[1;33mskip\033[0m through nginx (nginx not running yet)\n'
fi

if (( failed )); then
    cat <<EOF

Something is not answering. Check the logs:
    sudo journalctl -u drp-backend  -n 50 --no-pager
    sudo journalctl -u drp-frontend -n 50 --no-pager
    sudo journalctl -u drp-celery-worker -n 50 --no-pager
    sudo tail -n 50 /var/log/nginx/drp-error.log

To roll back to the previous release: sudo bash $APP_DIR/deploy/rollback.sh
EOF
    exit 1
fi

log "$(printf '\033[1;32mDeploy complete\033[0m')"
printf '    Release: %s\n' "$RELEASE_ID"
systemctl --no-pager --lines=0 status drp-backend drp-frontend drp-celery-worker drp-celery-beat | grep -E 'drp-|Active:'
