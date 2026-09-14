#!/usr/bin/env bash
#
# Copy the newest local backups to Google Drive, encrypted.
#
#   sudo bash /srv/agribiz-drp/deploy/offsite-backup.sh
#
# Runs automatically after every successful drp-backup.service (OnSuccess=
# drp-offsite-backup.service). Set up once with configure-offsite-backup.sh.
#
# Before 2026-09-14 backups existed only on this VPS, so a host failure would
# have taken the database and every restore point with it
# (docs/33_GO_LIVE_READINESS.md item 7).
#
# Files are encrypted by rclone's crypt remote before they leave the server:
# Google Drive holds only ciphertext with scrambled names. The rclone config
# holds the key -- without a copy of it kept off this server (see
# configure-offsite-backup.sh), the Drive copies cannot be decrypted.

set -euo pipefail

BACKUP_DIR="/srv/agribiz-drp/backups"
RCLONE_CONFIG="${DRP_RCLONE_CONFIG:-/etc/drp/rclone.conf}"
REMOTE="drp-offsite:"
REMOTE_RETENTION_DAYS="${DRP_OFFSITE_RETENTION_DAYS:-90}"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

if [[ ! -f "$RCLONE_CONFIG" ]]; then
    # Not configured yet is a state, not a failure: the local backup already
    # succeeded, and nothing here should turn the backup unit red.
    echo "Offsite backup not configured (no $RCLONE_CONFIG). Run configure-offsite-backup.sh."
    exit 0
fi
command -v rclone >/dev/null || die "rclone is not installed."

rc() { rclone --config "$RCLONE_CONFIG" "$@"; }

newest() { ls -t "$BACKUP_DIR"/$1 2>/dev/null | head -1; }
DB_DUMP="$(newest 'drp-*.sql.gz')"
FILES_TAR="$(newest 'drp-files-*.tar.gz')"
[[ -n "$DB_DUMP" ]] || die "No database backup found in $BACKUP_DIR."

log "Uploading to Google Drive (encrypted)"
for f in "$DB_DUMP" $FILES_TAR; do
    rc copyto "$f" "$REMOTE$(basename "$f")" --retries 5 --low-level-retries 10 || die "upload failed: $f"
    # Size check against what arrived, read back through the decryption layer.
    local_size="$(stat -c %s "$f")"
    remote_size="$(rc size --json "$REMOTE$(basename "$f")" | python3 -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')"
    [[ "$local_size" == "$remote_size" ]] || die "size mismatch for $(basename "$f"): local $local_size, Drive $remote_size"
    printf '    %s (%s bytes) verified\n' "$(basename "$f")" "$local_size"
done

log "Removing Drive copies older than $REMOTE_RETENTION_DAYS days"
rc delete "$REMOTE" --min-age "${REMOTE_RETENTION_DAYS}d" --include 'drp-*' -v 2>&1 | grep -i "deleted" || echo "    nothing to remove"

log "Offsite copies"
rc lsl "$REMOTE" | sort -k2,3 | tail -4
