#!/usr/bin/env bash
#
# Set up outgoing email (PDF copies of completed forms).
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-email.sh'
#
# Works with any SMTP provider. Common choices:
#   Google Workspace / Gmail  smtp.gmail.com       587  (an App Password, not the account password;
#                                                      needs 2-Step Verification on the account)
#   Microsoft 365             smtp.office365.com   587
#   Zoho Mail                 smtp.zoho.com        587
#   Brevo (free tier)         smtp-relay.brevo.com 587
# For mail that reliably reaches inboxes from @agribizframework.com, add the
# provider's SPF and DKIM DNS records at Namecheap first.
#
# Prompts for every value (the password without echo), writes them to
# backend/.env (backed up first), blanks email in .env.staging, restarts the
# backend and sends one test message to an address you choose.

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
STAGING_ENV="$BACKEND/.env.staging"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
grep -q "EMAIL_HOST" "$BACKEND/config/settings/base.py" || die "deploy the latest release first"

ask() {  # ask VAR "Prompt" "default"
    local reply
    read -rp "$2${3:+ [$3]}: " reply
    printf -v "$1" '%s' "${reply:-$3}"
}
# Any of these can be preset in the environment, so only the password is typed:
#   sudo PRESET_USER=abffst.research.cut@gmail.com bash configure-email.sh
ask EMAIL_HOST "SMTP server" "${PRESET_HOST:-smtp.gmail.com}"
ask EMAIL_PORT "SMTP port" "${PRESET_PORT:-587}"
ask EMAIL_HOST_USER "SMTP username (usually the full address)" "${PRESET_USER:-}"
read -rsp "SMTP password or app password: " EMAIL_HOST_PASSWORD; echo
ask DEFAULT_FROM_EMAIL "From (name and address)" "ABF-FST Research <${EMAIL_HOST_USER}>"
ask STUDY_REPLY_TO_EMAIL "Replies go to" "${PRESET_REPLY_TO:-$EMAIL_HOST_USER}"
ask TEST_TO "Send a test message to" "$EMAIL_HOST_USER"
[[ -n "$EMAIL_HOST_USER" && -n "$EMAIL_HOST_PASSWORD" ]] || die "username and password are required"

set_kv() {
    local file="$1" key="$2" value="$3" tmp
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" 'BEGIN{done=0}
        $0 ~ "^"k"=" { if (!done) { print k"="v; done=1 } ; next }
        { print }
        END { if (!done) print k"="v }' "$file" > "$tmp"
    cat "$tmp" > "$file"; rm -f "$tmp"
}

cp -p "$ENV_FILE" "$ENV_FILE.bak-$(date +%Y%m%d%H%M%S)"
USE_SSL=False; USE_TLS=True
[[ "$EMAIL_PORT" == "465" ]] && { USE_SSL=True; USE_TLS=False; }
set_kv "$ENV_FILE" EMAIL_BACKEND "django.core.mail.backends.smtp.EmailBackend"
set_kv "$ENV_FILE" EMAIL_HOST "$EMAIL_HOST"
set_kv "$ENV_FILE" EMAIL_PORT "$EMAIL_PORT"
set_kv "$ENV_FILE" EMAIL_HOST_USER "$EMAIL_HOST_USER"
set_kv "$ENV_FILE" EMAIL_HOST_PASSWORD "$EMAIL_HOST_PASSWORD"
set_kv "$ENV_FILE" EMAIL_USE_TLS "$USE_TLS"
set_kv "$ENV_FILE" EMAIL_USE_SSL "$USE_SSL"
set_kv "$ENV_FILE" DEFAULT_FROM_EMAIL "\"$DEFAULT_FROM_EMAIL\""
set_kv "$ENV_FILE" STUDY_REPLY_TO_EMAIL "$STUDY_REPLY_TO_EMAIL"
chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

# Staging must never email anyone.
if [[ -f "$STAGING_ENV" ]]; then
    set_kv "$STAGING_ENV" EMAIL_BACKEND "django.core.mail.backends.console.EmailBackend"
    set_kv "$STAGING_ENV" EMAIL_HOST ""
fi

echo "Restarting the backend..."
systemctl restart drp-backend
sleep 4

echo "Sending a test message to $TEST_TO..."
( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod TEST_TO="$TEST_TO" \
    "$BACKEND/venv/bin/python" manage.py shell -c "
import os
from django.core.mail import send_mail
send_mail('ABF-FST portal: email test', 'Outgoing email from research.agribizframework.com works.', None, [os.environ['TEST_TO']])
print('sent')
" 2>&1 | grep -vE "Warning|warn" ) || die "sending failed -- check the server, port, username and password"

echo "Done. Staff can now email PDF copies from the Form PDFs screen."
echo "Remember each staff account needs an email address (Account screen / Django admin)."
