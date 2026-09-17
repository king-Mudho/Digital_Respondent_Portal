#!/usr/bin/env bash
#
# Turn on AI-assisted drafting for the Document Analysis Tool.
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-coding.sh'
#
# Needs an Anthropic API key -- console.anthropic.com, an account with
# billing set up. This is a paid, per-request cost to the PI's own
# Anthropic account (roughly a few US cents per document, more for very
# long PDFs), not part of KoboToolbox or anything already running.
#
# What this does NOT do: turning this on does not make anything
# automatic. It only makes the "Auto-fill" button on a document's page
# produce a draft; a Documentary RA still reviews it and clicks Submit
# themselves before anything reaches KoboToolbox -- see
# apps/evidence/ai_coding.py's docstring for why that's not optional for
# this particular form.
#
# Prompts for the API key (without echo) and the Kobo account username
# (needed to submit a reviewed draft, not for drafting itself), writes
# them to backend/.env (backed up first), and restarts the backend.

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
grep -q "ANTHROPIC_API_KEY" "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates ANTHROPIC_API_KEY -- run deploy.sh with the latest release first"

read -rsp "Anthropic API key (sk-ant-...): " ANTHROPIC_API_KEY; echo
[[ -n "$ANTHROPIC_API_KEY" ]] || die "no API key given"

ask() {  # ask VAR "Prompt" "default"
    local reply
    read -rp "$2${3:+ [$3]}: " reply
    printf -v "$1" '%s' "${reply:-$3}"
}
# The Kobo account's own username (not a secret -- it's already visible in
# every KoboToolbox project URL), needed only so a reviewed draft can be
# submitted to the right account's OpenRosa endpoint.
ask KOBO_ACCOUNT_USERNAME "KoboToolbox account username" "${PRESET_KOBO_USERNAME:-mudho}"

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
set_kv "$ENV_FILE" ANTHROPIC_API_KEY "$ANTHROPIC_API_KEY"
set_kv "$ENV_FILE" AI_DOCUMENT_CODING_MODEL "claude-opus-5"
set_kv "$ENV_FILE" KOBO_OPENROSA_BASE_URL "https://kc.kobotoolbox.org"
set_kv "$ENV_FILE" KOBO_ACCOUNT_USERNAME "$KOBO_ACCOUNT_USERNAME"
chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

echo "Checking the key..."
( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
    "$BACKEND/venv/bin/python" manage.py shell -c "
import anthropic
from django.conf import settings
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
try:
    client.messages.create(model=settings.AI_DOCUMENT_CODING_MODEL, max_tokens=8,
                            messages=[{'role': 'user', 'content': 'say ok'}])
    print('key accepted')
except anthropic.AuthenticationError:
    raise SystemExit('the API key was rejected -- check it and re-run')
" ) || die "key check failed"

echo "Restarting the backend..."
systemctl restart drp-backend
sleep 4
systemctl is-active --quiet drp-backend || die "drp-backend did not come back up: journalctl -u drp-backend -n 50"

echo "Done. 'Auto-fill' now appears on a document's page once a source file is uploaded."
echo "Clear this terminal afterwards; the key above is also in $ENV_FILE."
