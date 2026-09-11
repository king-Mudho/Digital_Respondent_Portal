#!/usr/bin/env bash
#
# Back up the production PostgreSQL database.
#
#   sudo bash /srv/agribiz-drp/deploy/backup.sh
#
# docs/23_DEPLOYMENT_ARCHITECTURE.md RPO target: <= 4 hours during active
# fieldwork. deploy.sh calls this automatically before migrating; for the
# RPO target to actually hold, this also needs a cron/systemd-timer running
# it at least every 4 hours during Phases 1-3 -- not wired up automatically
# here since that cadence is a fieldwork-calendar decision, not a fixed
# constant (see docs/27_AGENT_EXECUTION_PLAN.md Phase 10's backup/restore
# drill item). Only handles local rotation -- copy backups off this server
# periodically too.

set -euo pipefail

DB_NAME="drp_prod"
BACKUP_DIR="/srv/agribiz-drp/backups"
RETENTION_DAYS="${DRP_BACKUP_RETENTION_DAYS:-14}"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$BACKUP_DIR/drp-$TIMESTAMP.sql.gz"

log "Backing up '$DB_NAME' to $OUT_FILE"
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$OUT_FILE" || die "pg_dump failed"

SIZE="$(du -h "$OUT_FILE" | cut -f1)"
printf '    Backup written: %s (%s)\n' "$OUT_FILE" "$SIZE"

log "Pruning backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'drp-*.sql.gz' -mtime "+$RETENTION_DAYS" -print -delete

log "Current backups"
ls -lh "$BACKUP_DIR"/drp-*.sql.gz 2>/dev/null || echo "    (none yet)"
