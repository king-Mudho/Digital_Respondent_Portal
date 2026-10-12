#!/usr/bin/env bash
#
# Switch on reading replies from the study mailbox into Communications (apps/messaging/mailbox.py, 2026-10-12).
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-email-inbox.sh'
#
# Uses the account and app password configure-email.sh already saved (nothing secret is typed here). Every few
# minutes the portal then reads new mail over IMAP and copies in only emails from or to an address on a Main-400 case
# or KII record; everything else is never copied. The mailbox is opened read-only: nothing is marked read, moved or
# deleted. For Gmail, IMAP is always on; the app password used for sending works for reading too.
#
# Run again and answer "off" to switch it off.

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
STAGING_ENV="$BACKEND/.env.staging"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
grep -q "EMAIL_IMAP_HOST" "$BACKEND/config/settings/base.py" || die "deploy the latest release first"
grep -q "^EMAIL_HOST_PASSWORD=." "$ENV_FILE" || die "outgoing email is not set up yet: run configure-email.sh first"

current() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
ask() {  # ask VAR "Prompt" "default"
    local reply
    read -rp "$2${3:+ [$3]}: " reply
    printf -v "$1" '%s' "${reply:-$3}"
}
CURRENT_HOST="$(current EMAIL_IMAP_HOST)"
ask EMAIL_IMAP_HOST "IMAP server (type off to stop reading)" "${CURRENT_HOST:-imap.gmail.com}"
[[ "$EMAIL_IMAP_HOST" == "off" ]] && EMAIL_IMAP_HOST=""
CURRENT_SENT="$(current EMAIL_SENT_FOLDER | tr -d '"')"
ask EMAIL_SENT_FOLDER "Sent folder to read as well (type none to skip)" "${CURRENT_SENT:-[Gmail]/Sent Mail}"
[[ "$EMAIL_SENT_FOLDER" == "none" ]] && EMAIL_SENT_FOLDER=""

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
set_kv "$ENV_FILE" EMAIL_IMAP_HOST "$EMAIL_IMAP_HOST"
set_kv "$ENV_FILE" EMAIL_SENT_FOLDER "\"$EMAIL_SENT_FOLDER\""
chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

# Staging must never read the study's real mailbox.
[[ -f "$STAGING_ENV" ]] && set_kv "$STAGING_ENV" EMAIL_IMAP_HOST ""

echo "Restarting the backend and the Celery worker..."
systemctl restart drp-backend drp-celery-worker
sleep 4
for service in drp-backend drp-celery-worker; do
    systemctl is-active --quiet "$service" || die "$service did not come back up: journalctl -u $service -n 50"
done

if [[ -z "$EMAIL_IMAP_HOST" ]]; then
    echo "Done. Reading the mailbox is off; replies stay in the mailbox only."
    exit 0
fi

echo "Checking the mailbox (read-only) and reading it once..."
( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
    "$BACKEND/venv/bin/python" manage.py shell -c "
from apps.messaging.mailbox import sync_mailbox
result = sync_mailbox()
if 'error' in result:
    raise SystemExit('Could not sign in: ' + result['error'])
from apps.messaging.models import MailboxCursor
for cursor in MailboxCursor.objects.all():
    state = ('NOT READ: ' + cursor.last_error) if cursor.last_error else 'read'
    print(f'  {cursor.folder}: {state}; {result.get(cursor.folder, 0)} email(s) copied in')
" 2>&1 | grep -vE "Warning|warn" ) || die "the mailbox could not be read -- check that IMAP is allowed for this account"

echo "Done. Communications now shows email replies from people on a case or KII record, checked every few minutes."
