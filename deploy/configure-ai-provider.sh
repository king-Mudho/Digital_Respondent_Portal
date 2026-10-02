#!/usr/bin/env bash
#
# Send AI document drafting to Meta's Model API (Muse Spark), or switch it back to Anthropic.
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh'            # to Meta
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh --revert'   # back to Anthropic
#
# Before you run it:
#   * You need a Meta Model API key (dev.meta.ai) on an account with billing set up. The key is typed here, hidden,
#     and written only to backend/.env -- never put it in a chat, an email or the repository.
#   * Turning this on sends the text of uploaded source documents to Meta (api.meta.ai) instead of Anthropic. The
#     Participant Information Sheet already says an AI tool from a company outside Zimbabwe is used; confirm that
#     the ethics position also covers Meta as the provider.
#   * It changes DOCUMENT CODING only. PROIT research stays on Anthropic, because its web search is an Anthropic tool.
#   * Nothing becomes automatic. A Documentary RA still reviews every draft before it can be submitted to KoboToolbox.
#
# What it does: backs up backend/.env, writes the three settings, runs `manage.py check_ai_provider` (synthetic
# content only: a number and a one-page invoice PDF) and, if ANY check fails, puts the old .env back and stops.
# Only when every check passes does it restart the backend and the Celery worker (drafts are written by the worker).

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
META_URL="https://api.meta.ai/v1"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
grep -q "AI_DOCUMENT_CODING_BASE_URL" "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates the provider setting -- run deploy.sh with the latest release first"

set_kv() {
    local file="$1" key="$2" value="$3" tmp
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" 'BEGIN{done=0}
        $0 ~ "^"k"=" { if (!done) { print k"="v; done=1 } ; next }
        { print }
        END { if (!done) print k"="v }' "$file" > "$tmp"
    cat "$tmp" > "$file"; rm -f "$tmp"
}

secure_env() { chown "$APP_USER:$APP_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"; }

restart_services() {
    echo "Restarting the backend and the Celery worker..."
    systemctl restart drp-backend drp-celery-worker
    sleep 4
    for unit in drp-backend drp-celery-worker; do
        systemctl is-active --quiet "$unit" || die "$unit did not come back up: journalctl -u $unit -n 50"
    done
}

BACKUP="$ENV_FILE.bak-$(date +%Y%m%d%H%M%S)"

if [[ "${1:-}" == "--revert" ]]; then
    cp -p "$ENV_FILE" "$BACKUP"
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_BASE_URL ""
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_API_KEY ""
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_MODEL "claude-opus-5"
    secure_env
    restart_services
    echo "Done. Document drafting is back on Anthropic (claude-opus-5). The previous .env is at $BACKUP."
    exit 0
fi

[[ -z "${1:-}" ]] || die "unknown option '$1' (the only option is --revert)"

read -rp "Model [muse-spark-1.3]: " MODEL
MODEL="${MODEL:-muse-spark-1.3}"
read -rsp "Meta Model API key: " META_KEY; echo
[[ -n "$META_KEY" ]] || die "no API key given"

cp -p "$ENV_FILE" "$BACKUP"
set_kv "$ENV_FILE" AI_DOCUMENT_CODING_BASE_URL "$META_URL"
set_kv "$ENV_FILE" AI_DOCUMENT_CODING_API_KEY "$META_KEY"
set_kv "$ENV_FILE" AI_DOCUMENT_CODING_MODEL "$MODEL"
secure_env

echo "Checking Meta with synthetic content only (no study data)..."
if ! ( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
        "$BACKEND/venv/bin/python" manage.py check_ai_provider ); then
    cp -p "$BACKUP" "$ENV_FILE"
    secure_env
    die "the check failed, so nothing was changed and the previous .env is back in place."
fi

restart_services
echo "Done. New drafts go to $META_URL using $MODEL. Each draft records which provider produced it."
echo "To go back to Anthropic at any time: sudo bash $0 --revert"
echo "Clear this terminal afterwards; the key is also in $ENV_FILE (mode 600)."
