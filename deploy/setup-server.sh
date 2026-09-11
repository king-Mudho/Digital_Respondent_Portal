#!/usr/bin/env bash
#
# One-time server provisioning for DRP, run on the same VPS as the sibling
# ABI project (66.29.139.201) after ABI's own setup-server.sh has already
# run (this script assumes nginx, PostgreSQL, Node 20, Python 3.12,
# firewalld, fail2ban and the 2GB swap file already exist -- it only adds
# what DRP needs on top).
#
#   sudo bash /srv/agribiz-drp/deploy/setup-server.sh
#
# Idempotent -- safe to re-run.

set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

log "Installing Redis (Celery broker -- the one thing ABI's own setup doesn't need)"
if ! rpm -q redis >/dev/null 2>&1; then
    dnf install -y redis
fi
# Broker-only workload: cap memory conservatively on this ~956MB box,
# shared with ABI's own full stack (docs/27_AGENT_EXECUTION_PLAN.md Phase 10).
sed -i 's/^# maxmemory .*/maxmemory 32mb/' /etc/redis/redis.conf
grep -q '^maxmemory ' /etc/redis/redis.conf || echo 'maxmemory 32mb' >> /etc/redis/redis.conf
sed -i 's/^# maxmemory-policy .*/maxmemory-policy noeviction/' /etc/redis/redis.conf
grep -q '^maxmemory-policy' /etc/redis/redis.conf || echo 'maxmemory-policy noeviction' >> /etc/redis/redis.conf
systemctl enable --now redis
systemctl restart redis

log "Creating the agribiz-drp system user (no login shell, no password)"
id agribiz-drp >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin agribiz-drp

# --no-create-home leaves /etc/passwd pointing at /home/agribiz-drp without
# the directory existing. Harmless until something needs a real writable
# HOME -- npm does, for its cache (~/.npm) during `npm ci`/`npm install`.
# Found the hard way during Phase 10's first deploy attempt: EACCES: mkdir
# '/home/agribiz-drp'. Create it explicitly rather than relying on a tool
# to fail loudly every time.
log "Creating a home directory for agribiz-drp (needed by npm's cache, not for login)"
mkdir -p /home/agribiz-drp
chown agribiz-drp:agribiz-drp /home/agribiz-drp
chmod 700 /home/agribiz-drp

log "Creating /srv/agribiz-drp directory structure"
mkdir -p /srv/agribiz-drp/{backend,frontend/releases,logs,backups}
chown -R agribiz-drp:agribiz-drp /srv/agribiz-drp

log "Creating the drp_user database role and drp_prod database"
echo "Run this manually with a real generated password (never hardcode one in this script):"
echo "  sudo -u postgres psql -c \"CREATE ROLE drp_user WITH LOGIN PASSWORD '<generated>';\""
echo "  sudo -u postgres createdb -O drp_user drp_prod"
echo "(Already done for this deployment -- documented here for reproducibility on a future box.)"

log "Opening no new firewall ports"
echo "Redis (127.0.0.1 only), Gunicorn (127.0.0.1:8100) and Node (127.0.0.1:3100) all"
echo "bind to loopback, same as ABI's own services -- nothing new to open. Only 80/443/22"
echo "are exposed externally, per ABI's setup-server.sh firewall step."

log "Setup complete. Next: rsync the code to /srv/agribiz-drp/{backend,frontend}, fill in"
log ".env from deploy/env-templates/, then run deploy.sh."
