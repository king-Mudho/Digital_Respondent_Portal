# Deployment scripts

Mirrors the sibling ABI project's `deploy/` layout and conventions (same VPS, same
lessons about Certbot ownership of the `:443` block -- see that project's
`docs/PRODUCTION_ARCHITECTURE.md` "The 127.0.0.1 lesson", which applies unchanged here).

| File | Purpose |
|---|---|
| `setup-server.sh` | One-time provisioning: Redis, the `agribiz-drp` system user, `/srv/agribiz-drp/` directories. Idempotent. |
| `deploy.sh` | Build and (re)start the app: installs deps, migrates, collects static, builds the frontend, restarts all four systemd services, validates/installs nginx, runs health checks. Run for every deploy after the first. |
| `backup.sh` | `pg_dump` of `drp_prod`, gzip-compressed, rotated. Called automatically by `deploy.sh` before migrating. |
| `rollback.sh` | Roll back the frontend release and/or backend commit; optional (confirmed, destructive) database restore. |
| `gunicorn.conf.py` | Gunicorn config -- 1 worker, 2 threads, tuned for this VPS now running two full app stacks (see `docs/27_AGENT_EXECUTION_PLAN.md` Phase 10). |
| `env-templates/*.env.production` | `.env` templates with placeholder secrets -- never commit the filled-in files. |

See the repository root `docs/DEPLOYMENT.md` for the full walkthrough (server details, DNS,
SSL, the four systemd units including Celery worker + Beat, troubleshooting).

## Backup & restore

```bash
sudo bash /srv/agribiz-drp/deploy/backup.sh
sudo bash /srv/agribiz-drp/deploy/rollback.sh --restore-db /srv/agribiz-drp/backups/drp-<timestamp>.sql.gz
```

docs/23_DEPLOYMENT_ARCHITECTURE.md's RPO target (<=4 hours during active fieldwork)
requires `backup.sh` to also run on a cron/systemd-timer at that cadence during Phases
1-3 -- not wired up automatically, since the cadence depends on the fieldwork calendar.
