#!/usr/bin/env bash
#
# Roll back to the previous frontend release and/or a previous backend
# commit. Does NOT touch the database by default -- see --restore-db.
#
# Usage:
#   sudo bash /srv/agribiz-drp/deploy/rollback.sh
#   sudo bash /srv/agribiz-drp/deploy/rollback.sh --backend <git-sha>
#   sudo bash /srv/agribiz-drp/deploy/rollback.sh --restore-db /srv/agribiz-drp/backups/drp-<ts>.sql.gz

set -euo pipefail

APP_USER="agribiz-drp"
APP_DIR="/srv/agribiz-drp"
BACKEND="$APP_DIR/backend"
FRONTEND="$APP_DIR/frontend"
DB_NAME="drp_prod"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this with sudo."

BACKEND_SHA=""
RESTORE_DB=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)    BACKEND_SHA="$2"; shift 2 ;;
        --restore-db) RESTORE_DB="$2"; shift 2 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

log "Rolling back frontend to the previous release"
CURRENT_TARGET="$(readlink -f "$FRONTEND/current" || true)"
mapfile -t releases < <(ls -1 "$FRONTEND/releases" 2>/dev/null | sort -r)

if [[ ${#releases[@]} -lt 2 ]]; then
    warn "Fewer than 2 releases exist under $FRONTEND/releases -- nothing to roll back to."
else
    PREVIOUS=""
    for r in "${releases[@]}"; do
        if [[ "$FRONTEND/releases/$r" != "$CURRENT_TARGET" ]]; then
            PREVIOUS="$r"
            break
        fi
    done
    if [[ -z "$PREVIOUS" ]]; then
        warn "Could not determine the previous release -- leaving 'current' untouched."
    else
        log "Switching current -> $PREVIOUS"
        ln -sfn "$FRONTEND/releases/$PREVIOUS" "$FRONTEND/current"
        chown -h "$APP_USER:$APP_USER" "$FRONTEND/current"
        systemctl restart drp-frontend
        printf '    Frontend now serving release: %s\n' "$PREVIOUS"
    fi
fi

if [[ -n "$BACKEND_SHA" ]]; then
    log "Rolling back backend code to $BACKEND_SHA"
    [[ -d "$BACKEND/.git" ]] || die "$BACKEND is not a git checkout -- cannot roll back by commit."
    CURRENT_SHA="$(cd "$BACKEND" && git rev-parse HEAD)"
    printf '    Current commit:  %s\n' "$CURRENT_SHA"
    printf '    Rolling back to: %s\n' "$BACKEND_SHA"
    ( cd "$BACKEND" && git checkout "$BACKEND_SHA" -- . )
    sudo -u "$APP_USER" "$BACKEND/venv/bin/pip" install --quiet -r "$BACKEND/requirements/prod.txt"
    warn "Migrations are NOT automatically reversed. Restore a matching database backup"
    warn "too (--restore-db) if this release depends on one the rolled-back code doesn't."
    systemctl restart drp-backend
fi

if [[ -n "$RESTORE_DB" ]]; then
    [[ -f "$RESTORE_DB" ]] || die "Backup file not found: $RESTORE_DB"

    echo
    printf '\033[1;31mThis will DROP and RECREATE %s from:\033[0m\n' "$DB_NAME"
    printf '    %s\n' "$RESTORE_DB"
    printf 'Every write to the database since that backup was taken will be LOST.\n'
    read -r -p "Type the database name ($DB_NAME) to confirm: " CONFIRM
    [[ "$CONFIRM" == "$DB_NAME" ]] || die "Confirmation did not match -- aborting, nothing was touched."

    log "Stopping backend and Celery so nothing writes during restore"
    systemctl stop drp-backend drp-celery-worker drp-celery-beat

    log "Restoring $DB_NAME from $RESTORE_DB"
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${DB_NAME}_restoring;" >/dev/null
    sudo -u postgres createdb -O drp_user "${DB_NAME}_restoring"
    gunzip -c "$RESTORE_DB" | sudo -u postgres psql -d "${DB_NAME}_restoring" >/dev/null
    sudo -u postgres psql -c "ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_pre_restore_$(date +%s);"
    sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME}_restoring RENAME TO $DB_NAME;"

    log "Restarting services"
    systemctl start drp-backend drp-celery-worker drp-celery-beat
    printf '    Restored. The pre-restore database was kept as %s_pre_restore_<timestamp>\n' "$DB_NAME"
    printf '    rather than dropped -- remove it manually once the restore is confirmed good.\n'
fi

log "Rollback steps complete."
