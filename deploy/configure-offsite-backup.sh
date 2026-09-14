#!/usr/bin/env bash
#
# One-time setup of encrypted offsite backups to Google Drive.
#
# Run from your own computer, so the Google sign-in opens in your browser
# through an SSH tunnel:
#
#   ssh -t -L 53682:127.0.0.1:53682 agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-offsite-backup.sh'
#
# What it does:
#   1. Installs rclone (EPEL) if missing.
#   2. Signs in to Google Drive with the narrowest scope rclone offers
#      (drive.file: this server sees only files it created, not the rest of
#      the Drive). You open the printed link, choose the Google account, allow.
#   3. Creates an encryption layer (rclone crypt) over the folder
#      "ABF-FST-DRP-backups", with a random password and salt.
#   4. Uploads the newest backup, downloads it back, decrypts it and checks the
#      gzip and the SQL inside -- a restore test, not just an upload test.
#   5. Installs drp-offsite-backup.service, triggered after every successful
#      drp-backup.service run.
#
# Safe to re-run: an existing configuration is kept unless you pass --reset.

set -euo pipefail

APP_DIR="/srv/agribiz-drp"
CONF_DIR="/etc/drp"
RCLONE_CONFIG="$CONF_DIR/rclone.conf"
DRIVE_FOLDER="ABF-FST-DRP-backups"
BACKUP_DIR="$APP_DIR/backups"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"

if [[ "${1:-}" == "--reset" && -f "$RCLONE_CONFIG" ]]; then
    mv "$RCLONE_CONFIG" "$RCLONE_CONFIG.old-$(date +%Y%m%d%H%M%S)"
fi

if ! command -v rclone >/dev/null; then
    log "Installing rclone"
    dnf install -y rclone >/dev/null
fi
rclone version | head -1

install -d -m 700 "$CONF_DIR"
rc() { rclone --config "$RCLONE_CONFIG" "$@"; }

if ! rc listremotes 2>/dev/null | grep -q '^gdrive:$'; then
    log "Google Drive sign-in"
    cat <<'EOF'
    rclone now starts a sign-in page on port 53682 and prints a link.
    Open that link in the browser on YOUR computer (the ssh -L tunnel carries
    it here), choose the Google account that should hold the backups, and allow
    access. Google may warn that rclone is not verified by Google -- that is the
    standard open-source rclone client; continue.
EOF
    rc config create gdrive drive scope=drive.file config_is_local=true config_team_drive=false
    rc listremotes | grep -q '^gdrive:$' || die "Google Drive sign-in did not complete."
fi

if ! rc listremotes | grep -q '^drp-offsite:$'; then
    log "Creating the encryption layer"
    PASSWORD="$(openssl rand -base64 48 | tr -d '\n')"
    SALT="$(openssl rand -base64 48 | tr -d '\n')"
    rc config create drp-offsite crypt remote="gdrive:$DRIVE_FOLDER" \
        filename_encryption=standard directory_name_encryption=true \
        password="$PASSWORD" password2="$SALT" --obscure >/dev/null
    # Plain copy of the two secrets for the PI to store off this server. The
    # rclone.conf holds them too, but obscured -- that is not encryption.
    umask 077
    printf 'ABF-FST DRP offsite backup key (rclone crypt)\ncreated %s\nremote gdrive:%s\npassword  %s\npassword2 %s\n' \
        "$(date -u +%FT%TZ)" "$DRIVE_FOLDER" "$PASSWORD" "$SALT" > "$CONF_DIR/offsite-backup-key.txt"
    unset PASSWORD SALT
fi
chmod 600 "$RCLONE_CONFIG" "$CONF_DIR"/offsite-backup-key.txt 2>/dev/null || true

log "Uploading the newest backup"
bash "$APP_DIR/deploy/offsite-backup.sh"

log "Restore test: download, decrypt, verify"
DB_DUMP="$(ls -t "$BACKUP_DIR"/drp-*.sql.gz | head -1)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rc copyto "drp-offsite:$(basename "$DB_DUMP")" "$TMP/restore.sql.gz"
cmp -s "$DB_DUMP" "$TMP/restore.sql.gz" || die "downloaded copy differs from the local backup"
gzip -t "$TMP/restore.sql.gz" || die "downloaded copy is not a valid gzip"
zcat "$TMP/restore.sql.gz" | grep -q "PostgreSQL database dump complete" || die "dump is incomplete"
TABLES="$(zcat "$TMP/restore.sql.gz" | grep -c '^CREATE TABLE')"
printf '    identical to the local file, valid gzip, complete dump, %s tables\n' "$TABLES"

log "Confirming Google only holds ciphertext"
rc lsf gdrive:"$DRIVE_FOLDER" | head -3 | sed 's/^/    /'

log "Installing the automatic upload"
install -m 644 "$APP_DIR/systemd/drp-offsite-backup.service" /etc/systemd/system/
mkdir -p /etc/systemd/system/drp-backup.service.d
cat > /etc/systemd/system/drp-backup.service.d/offsite.conf <<'EOF'
[Unit]
OnSuccess=drp-offsite-backup.service
EOF
systemctl daemon-reload

cat <<EOF

Offsite backups are on. Every successful 4-hourly backup is now encrypted and
copied to Google Drive (folder "$DRIVE_FOLDER"), kept for 90 days.

IMPORTANT -- keep the key somewhere other than this server:
  sudo cat $CONF_DIR/offsite-backup-key.txt
Store both lines in a password manager. If this server is lost, the Drive
copies cannot be decrypted without them. Restore steps: docs/23 "Offsite backups".
EOF
