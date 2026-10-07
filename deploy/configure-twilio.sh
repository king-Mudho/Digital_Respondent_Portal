#!/usr/bin/env bash
#
# Set up SMS and WhatsApp sending through Twilio (invitations, and the automatic Day 2 / Day 7 reminders).
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-twilio.sh'
#
# What you need from the Twilio console (twilio.com/console), on an upgraded (not trial) account with credit:
#   Account SID and Auth Token   Account > API keys & tokens (the Auth Token is typed without echo)
#   SMS sender                   a sender name registered for Zimbabwe (e.g. CUT-ABFFST), or an international
#                                number in +E.164 form. Leave blank to keep SMS switched off.
#   WhatsApp sender              the number registered as a WhatsApp sender on Twilio, +E.164. Leave blank until
#                                Meta has approved it.
#   WhatsApp templates           the HX... ids of the Meta-approved templates in Twilio's Content Template Builder:
#                                Main-400 invitation and KII invitation ({{1}} who it is for, {{2}} link,
#                                {{3}} valid-until date, {{4}} code), Day 2 and Day 7 reminders (no variables).
# Also switch on Zimbabwe under Messaging > Settings > Geo permissions.
#
# Every value already set is offered as the default, so you can re-run this to add the WhatsApp values later; press
# Enter at the Auth Token prompt to keep the saved one. Writes backend/.env (backed up first), blanks Twilio in
# .env.staging (staging must never message anyone), restarts the backend and the Celery worker, and sends one test
# SMS to a number you choose -- never to a respondent.

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
STAGING_ENV="$BACKEND/.env.staging"
TWILIO_KEYS=(TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_SMS_FROM TWILIO_WHATSAPP_FROM TWILIO_WA_CONTENT_INVITATION
             TWILIO_WA_CONTENT_KII_INVITATION TWILIO_WA_CONTENT_REMINDER_DAY2 TWILIO_WA_CONTENT_REMINDER_DAY7)

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
grep -q "TWILIO_ACCOUNT_SID" "$BACKEND/config/settings/base.py" || die "deploy the latest release first"

current() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
ask() {  # ask VAR "Prompt" -- the saved value is the default
    local reply saved
    saved="$(current "$1")"
    read -rp "$2${saved:+ [$saved]}: " reply
    printf -v "$1" '%s' "${reply:-$saved}"
}

ask TWILIO_ACCOUNT_SID "Twilio Account SID (starts AC)"
read -rsp "Twilio Auth Token (Enter keeps the saved one): " TWILIO_AUTH_TOKEN; echo
TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-$(current TWILIO_AUTH_TOKEN)}"
ask TWILIO_SMS_FROM "SMS sender: registered name or +number (blank = SMS off)"
ask TWILIO_WHATSAPP_FROM "WhatsApp sender +number (blank = WhatsApp off)"
ask TWILIO_WA_CONTENT_INVITATION "WhatsApp template id: Main-400 invitation (HX...)"
ask TWILIO_WA_CONTENT_KII_INVITATION "WhatsApp template id: KII invitation (HX...)"
ask TWILIO_WA_CONTENT_REMINDER_DAY2 "WhatsApp template id: Day 2 reminder (HX...)"
ask TWILIO_WA_CONTENT_REMINDER_DAY7 "WhatsApp template id: Day 7 reminder (HX...)"
read -rp "Send a test SMS to (your own mobile, e.g. 0771234567): " TEST_TO

[[ "$TWILIO_ACCOUNT_SID" == AC* ]] || die "the Account SID starts with AC"
[[ -n "$TWILIO_AUTH_TOKEN" ]] || die "the Auth Token is required"

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
for key in "${TWILIO_KEYS[@]}"; do
    set_kv "$ENV_FILE" "$key" "${!key}"
done
chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

# Staging must never message anyone.
if [[ -f "$STAGING_ENV" ]]; then
    for key in "${TWILIO_KEYS[@]}"; do set_kv "$STAGING_ENV" "$key" ""; done
fi

# The worker too: batches and the morning reminder run are sent by Celery, and each process reads .env only when it
# starts (the lesson of configure-email.sh, 2026-10-04).
echo "Restarting the backend and the Celery worker..."
systemctl restart drp-backend drp-celery-worker
sleep 4
for service in drp-backend drp-celery-worker; do
    systemctl is-active --quiet "$service" || die "$service did not come back up: journalctl -u $service -n 50"
done

run() { ( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
    "$BACKEND/venv/bin/python" manage.py "$@" 2>&1 | grep -vE "Warning|warn" ); }

if [[ -n "$TWILIO_SMS_FROM" && -n "$TEST_TO" ]]; then
    echo "Sending a test SMS to $TEST_TO..."
    run twilio_test --to "$TEST_TO" || die "the test SMS was not sent -- check the SID, token, sender and Geo permissions"
fi
if [[ -n "$TWILIO_WHATSAPP_FROM" && -n "$TWILIO_WA_CONTENT_INVITATION" && -n "$TEST_TO" ]]; then
    read -rp "Also send a test WhatsApp (the invitation template, to the same number)? [y/N] " WA_TEST
    if [[ "$WA_TEST" =~ ^[Yy] ]]; then
        run twilio_test --to "$TEST_TO" --whatsapp || die "the test WhatsApp was not sent -- check the sender and template id"
    fi
fi

echo "Done. Switched on: SMS ${TWILIO_SMS_FROM:+yes}${TWILIO_SMS_FROM:-no}; WhatsApp invitations"\
" ${TWILIO_WA_CONTENT_INVITATION:+yes}${TWILIO_WA_CONTENT_INVITATION:-no}."
echo "The morning reminder run (08:00) now sends due Day 2 / Day 7 reminders automatically on the channels switched on."
