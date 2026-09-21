#!/usr/bin/env bash
# Connect production to the main-study KoboToolbox Questionnaire.
#
#   sudo bash /srv/agribiz-drp/deploy/configure-kobo.sh
#
# Run AFTER deploy.sh has put commit 1b3845c or later on the server (the
# KOBO_FORM_URL setting does not exist before it). Safe to re-run: existing
# values are replaced in place, an existing webhook secret is kept, and
# backend/.env is backed up first.
#
# What it does:
#   1. Writes the seven KOBO_* settings into backend/.env. The API token is
#      read from a hidden prompt (or $KOBO_API_TOKEN), never stored in this repo.
#   2. Blanks the same settings in backend/.env.staging, which otherwise
#      inherits them -- staging must never pull the production form
#      (docs/24_ENVIRONMENT_CONFIGURATION.md).
#   3. Checks the token can read the project before restarting anything.
#   4. Restarts the backend and Celery, runs one manual sync, and prints the
#      webhook secret to paste into KoboToolbox's REST Service.
set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
STAGING_ENV="$BACKEND/.env.staging"

# The main-study Questionnaire project (mudho account), checked 2026-09-14:
# r2 XLSForm deployed, anonymous submissions allowed, 0 submissions.
KOBO_API_BASE_URL="https://kf.kobotoolbox.org"
KOBO_ASSET_UID="aefzZwVQV927tqtTgsP9oz"
KOBO_FORM_URL="https://ee.kobotoolbox.org/x/fSOJejrV"
# The other two main-study forms, read on demand for PDF copies (not reconciled).
# KII Guide r3 (2026-09-21): a NEW project, replacing an49gwkpkGfYjS6B4NDNqh (End time check repaired).
KOBO_KII_ASSET_UID="ar47NkjJiuWP4j6sTgmMpH"
KOBO_DOCUMENTS_ASSET_UID="a3vpgw6T4FbZGjQqmUgBND"
# The Document Analysis Tool's public web-form link (PI, 2026-09-17) -- powers
# the document page's "Code this document" prefilled link (apps/evidence).
KOBO_DOCUMENTS_FORM_URL="https://ee.kobotoolbox.org/x/nM616hqU"
# The Main Study KII Guide's public web-form link (PI, 2026-09-17) -- powers
# the KII page's "Continue this interview" prefilled link (apps/kii).
KOBO_KII_FORM_URL="https://ee.kobotoolbox.org/x/hwMQ5dG3"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
[[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found"
grep -q KOBO_FORM_URL "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates KOBO_FORM_URL -- run deploy.sh with the latest release first"
grep -q KOBO_DOCUMENTS_FORM_URL "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates KOBO_DOCUMENTS_FORM_URL -- run deploy.sh with the latest release first"
grep -q KOBO_KII_FORM_URL "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates KOBO_KII_FORM_URL -- run deploy.sh with the latest release first"

if [[ -z "${KOBO_API_TOKEN:-}" ]]; then
    read -rsp "KoboToolbox API token: " KOBO_API_TOKEN; echo
fi
[[ -n "$KOBO_API_TOKEN" ]] || die "no API token given"

echo "Checking the token can read the Questionnaire project..."
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Token $KOBO_API_TOKEN" \
    "$KOBO_API_BASE_URL/api/v2/assets/$KOBO_ASSET_UID/?format=json")"
[[ "$code" == "200" ]] || die "KoboToolbox answered HTTP $code for the project -- check the token"

set_kv() {  # set_kv FILE KEY VALUE -- replace the line if present, else append
    local file="$1" key="$2" value="$3" tmp
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" 'BEGIN{done=0}
        $0 ~ "^"k"=" { if (!done) { print k"="v; done=1 } ; next }
        { print }
        END { if (!done) print k"="v }' "$file" > "$tmp"
    cat "$tmp" > "$file"; rm -f "$tmp"
}

cp -p "$ENV_FILE" "$ENV_FILE.bak-$(date +%Y%m%d%H%M%S)"

secret="$(grep -E '^KOBO_WEBHOOK_SHARED_SECRET=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
if [[ -z "$secret" || "$secret" == "changeme" ]]; then
    secret="$(openssl rand -base64 36 | tr -d '/+=\n')"
fi

set_kv "$ENV_FILE" KOBO_API_BASE_URL "$KOBO_API_BASE_URL"
set_kv "$ENV_FILE" KOBO_ASSET_UID "$KOBO_ASSET_UID"
set_kv "$ENV_FILE" KOBO_API_TOKEN "$KOBO_API_TOKEN"
set_kv "$ENV_FILE" KOBO_FORM_URL "$KOBO_FORM_URL"
set_kv "$ENV_FILE" KOBO_WEBHOOK_SHARED_SECRET "$secret"
set_kv "$ENV_FILE" KOBO_KII_ASSET_UID "$KOBO_KII_ASSET_UID"
set_kv "$ENV_FILE" KOBO_DOCUMENTS_ASSET_UID "$KOBO_DOCUMENTS_ASSET_UID"
set_kv "$ENV_FILE" KOBO_DOCUMENTS_FORM_URL "$KOBO_DOCUMENTS_FORM_URL"
set_kv "$ENV_FILE" KOBO_KII_FORM_URL "$KOBO_KII_FORM_URL"
chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

if [[ -f "$STAGING_ENV" ]]; then
    for key in KOBO_ASSET_UID KOBO_API_TOKEN KOBO_FORM_URL KOBO_WEBHOOK_SHARED_SECRET KOBO_KII_ASSET_UID KOBO_DOCUMENTS_ASSET_UID KOBO_DOCUMENTS_FORM_URL KOBO_KII_FORM_URL; do
        set_kv "$STAGING_ENV" "$key" ""
    done
    chown "$APP_USER:$APP_USER" "$STAGING_ENV"
    echo "Staging: Kobo settings blanked (staging shows 'not connected')."
fi

echo "Restarting backend and Celery..."
systemctl restart drp-backend drp-celery-worker drp-celery-beat
sleep 5
systemctl is-active --quiet drp-backend || die "drp-backend did not come back up: journalctl -u drp-backend -n 50"

echo "Running one manual sync..."
( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
    "$BACKEND/venv/bin/python" manage.py shell -c "
from apps.kobo.services import reconcile, redirect_is_configured, reconciliation_is_configured
print('questionnaire link configured:', redirect_is_configured())
print('reconciliation configured:   ', reconciliation_is_configured())
log = reconcile()
print('sync:', 'FAILED -- ' + log.error_message if log.error_message else
      f'ok -- {log.submissions_pulled} pulled, {log.new_submissions} new, {log.mismatches_flagged} unmatched')
" )

echo "Checking the webhook accepts the secret..."
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Kobo-Shared-Secret: $secret" \
    https://research.agribizframework.com/api/v1/kobo/webhook/)"
echo "webhook: HTTP $code (202 expected)"

cat <<EOF

Done. Last step, in KoboToolbox (one time):
  Main Study Questionnaire -> Settings -> REST Services -> Register a new service
    Name:           ABF-FST Research Portal
    Endpoint URL:   https://research.agribizframework.com/api/v1/kobo/webhook/
    Type:           JSON
    Custom header:  X-Kobo-Shared-Secret   =   $secret
    Select fields:  _uuid   (the portal ignores the body and pulls data by API)

Clear this terminal afterwards; the secret above is also in $ENV_FILE.
EOF
