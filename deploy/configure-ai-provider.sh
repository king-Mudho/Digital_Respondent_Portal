#!/usr/bin/env bash
#
# Send AI work to Meta's Model API (Muse Spark), or switch it back to Anthropic.
#
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh'                   # documents to Meta
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh --revert'          # documents back
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh --proit'           # PROIT to Meta
#   ssh -t agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-ai-provider.sh --proit --revert'  # PROIT back
#
# Before you run it:
#   * You need a Meta Model API key (dev.meta.ai) on an account with billing set up. The key is typed here, hidden,
#     and written only to backend/.env -- never put it in a chat, an email or the repository.
#   * Documents: the text of uploaded source files goes to Meta (api.meta.ai) instead of Anthropic.
#   * PROIT: the organisation's name and details and the respondent's name and job title go to Meta, as the
#     Participant Information Sheet already describes for "an AI tool provided by a company outside Zimbabwe".
#     Meta's search cannot be told to avoid social-media pages; the portal drops those sources afterwards.
#     Switch PROIT only after the compare_proit_models review has passed.
#   * Nothing becomes automatic. A person still reviews every draft and every proposed fact.
#
# What it does: backs up backend/.env, writes the settings, runs `manage.py check_ai_provider` (synthetic content
# only) and, if ANY check fails, puts the old .env back and stops. Only when every check passes does it restart the
# backend and the Celery worker (drafts and research runs are done by the worker).

set -euo pipefail

APP_USER="agribiz-drp"
BACKEND="/srv/agribiz-drp/backend"
ENV_FILE="$BACKEND/.env"
META_URL="https://api.meta.ai/v1"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"

MODE="documents"; REVERT=0
for arg in "$@"; do
    case "$arg" in
        --proit) MODE="proit" ;;
        --revert) REVERT=1 ;;
        *) die "unknown option '$arg' (the options are --proit and --revert)" ;;
    esac
done

marker="AI_DOCUMENT_CODING_BASE_URL"; [[ "$MODE" == "proit" ]] && marker="AI_PROIT_PROVIDER"
grep -q "$marker" "$BACKEND/config/settings/base.py" \
    || die "the deployed code predates this setting -- run deploy.sh with the latest release first"

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

if [[ $REVERT -eq 1 ]]; then
    cp -p "$ENV_FILE" "$BACKUP"
    if [[ "$MODE" == "proit" ]]; then
        set_kv "$ENV_FILE" AI_PROIT_PROVIDER "anthropic"
        set_kv "$ENV_FILE" AI_PROIT_API_KEY ""
        set_kv "$ENV_FILE" AI_PROIT_RESEARCH_MODEL "claude-sonnet-5"
        done_msg="PROIT research is back on Anthropic (claude-sonnet-5)."
    else
        set_kv "$ENV_FILE" AI_DOCUMENT_CODING_BASE_URL ""
        set_kv "$ENV_FILE" AI_DOCUMENT_CODING_API_KEY ""
        set_kv "$ENV_FILE" AI_DOCUMENT_CODING_MODEL "claude-opus-5"
        done_msg="Document drafting is back on Anthropic (claude-opus-5)."
    fi
    secure_env
    restart_services
    echo "Done. $done_msg The previous .env is at $BACKUP."
    exit 0
fi

if [[ "$MODE" == "proit" ]]; then
    read -rp "Has the five-company comparison (compare_proit_models) been reviewed and passed? [y/N]: " PASSED
    [[ "$PASSED" =~ ^[Yy] ]] || die "switch PROIT only after the comparison has passed. Nothing was changed."
fi

read -rp "Model [muse-spark-1.3]: " MODEL
MODEL="${MODEL:-muse-spark-1.3}"
[[ "$MODEL" == *-contributor ]] && die "contributor models let Meta train on what is sent; use a Standard model"
read -rsp "Meta Model API key: " META_KEY; echo
[[ -n "$META_KEY" ]] || die "no API key given"

cp -p "$ENV_FILE" "$BACKUP"
if [[ "$MODE" == "proit" ]]; then
    set_kv "$ENV_FILE" AI_PROIT_PROVIDER "meta"
    set_kv "$ENV_FILE" AI_PROIT_API_KEY "$META_KEY"
    set_kv "$ENV_FILE" AI_PROIT_RESEARCH_MODEL "$MODEL"
    CHECK_ARGS="--proit"
else
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_BASE_URL "$META_URL"
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_API_KEY "$META_KEY"
    set_kv "$ENV_FILE" AI_DOCUMENT_CODING_MODEL "$MODEL"
    CHECK_ARGS=""
fi
secure_env

echo "Checking Meta with synthetic content only (no study data)..."
if ! ( cd "$BACKEND" && sudo -u "$APP_USER" env DJANGO_SETTINGS_MODULE=config.settings.prod \
        "$BACKEND/venv/bin/python" manage.py check_ai_provider $CHECK_ARGS ); then
    cp -p "$BACKUP" "$ENV_FILE"
    secure_env
    die "the check failed, so nothing was changed and the previous .env is back in place."
fi

restart_services
if [[ "$MODE" == "proit" ]]; then
    echo "Done. New PROIT research runs go to Meta using $MODEL. Each run's audit entry records the provider."
    echo "To go back to Anthropic at any time: sudo bash $0 --proit --revert"
else
    echo "Done. New drafts go to $META_URL using $MODEL. Each draft records which provider produced it."
    echo "To go back to Anthropic at any time: sudo bash $0 --revert"
fi
echo "Clear this terminal afterwards; the key is also in $ENV_FILE (mode 600)."
