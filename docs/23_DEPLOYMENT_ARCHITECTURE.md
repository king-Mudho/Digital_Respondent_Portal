# 23 — Deployment architecture

This closes two QC review gaps: no dev/staging/prod or CI strategy was named, and no
backup RPO/RTO targets were defined.

## Topology

```
Domain: research.agribizframework.com
        │
        ▼
   Nginx (reverse proxy, HTTPS via Let's Encrypt/Certbot — shared instance with ABI,
          separate server{} block for this subdomain)
        │
        ├──────────────► Next.js frontend (build + serve)
        │
        └──────────────► Django REST API (Gunicorn)
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
               PostgreSQL           Celery worker + Beat
               (drp_db)             (reconciliation, reminders)
                                          │
                                          ▼
                                        Redis
```

See `20_EMBEDDING_WITH_ABI.md` for what is and is not shared with the ABI deployment, and
the ABI project's own `PRODUCTION_ARCHITECTURE.md` for host-level lessons (the
Certbot/`127.0.0.1` health-check pitfall, the admin-path-collision fix) that apply
unchanged to this deployment on the same host.

## Environments and CI/CD strategy

Three environments, matching the original blueprint's own Section 22 requirement to
"test with synthetic/test cases only" before live use — which is not executable without
a real staging environment:

| Environment | Purpose | Kobo asset | Data |
|---|---|---|---|
| **Local/dev** | Individual developer machines | Dedicated Kobo test/staging asset (`11_KOBOTOOLBOX_INTEGRATION.md`) | Synthetic fixtures only |
| **Staging** | Pre-live rehearsal, UAT (`27_AGENT_EXECUTION_PLAN.md` Phase 5) | Same Kobo test/staging asset as dev | Synthetic/test cases only — never real Main-400 records |
| **Production** | Live fieldwork | Live production Kobo asset | Real Main-400/Reserve-400 data, from go-live onward |

**CI pipeline** (GitHub Actions or equivalent, run on every push/PR): lint
(ESLint/Ruff or flake8), type-check (`tsc --noEmit`), backend `pytest`, frontend Vitest,
and — on merge to the staging/production-tracking branches — the Playwright E2E suite
against a fresh database. A phase in `27_AGENT_EXECUTION_PLAN.md` is not markable
complete until CI is green for that phase's changes, mirroring the ABI project's own
`19_TESTING_STRATEGY.md` CI expectation.

**Promotion rule**: staging is rehearsed against the full `28_DEFINITION_OF_DONE.md`
go-live checklist before every production deploy during active fieldwork, and — per the
original blueprint's Section 21 — high-risk changes are frozen in the final two weeks
before the 30 November data lock except security/critical fixes.

## Process management

- Django: Gunicorn behind Nginx, managed by `systemd` (`drp-backend.service`).
- Celery worker + Beat: two further `systemd` units (`drp-celery-worker.service`,
  `drp-celery-beat.service`) — the reconciliation and reminder jobs must survive a
  server reboot without manual restart.
- Next.js: production build under `systemd` (`drp-frontend.service`) — never `next dev`
  in production.
- PostgreSQL and Redis: managed service or `systemd`-managed local instances.

## Backups & recovery — RPO/RTO targets

| Target | Value | Rationale |
|---|---|---|
| **Recovery Point Objective (RPO)** | ≤ 4 hours during active fieldwork (Phases 1–3); ≤ 24 hours otherwise | Fieldwork-window data (consent, QA decisions, reserve activations) is expensive and time-sensitive to recreate — a tighter RPO than a typical low-traffic app is justified specifically during collection. |
| **Recovery Time Objective (RTO)** | ≤ 4 hours during active fieldwork; ≤ 24 hours otherwise | A multi-day outage during the September–November collection window directly threatens the 30 November data lock. |

### Staging

ResearchOS brief §18.2 asks for a staging environment so production stops being the
place changes are first tried. As built (2026-09-14):

| | Production | Staging |
|---|---|---|
| Database | `drp_prod` | `drp_staging` |
| Backend | `drp-backend`, port 8100, always on | `drp-staging-backend`, port 8101, **on demand** |
| Frontend | `drp-frontend`, port 3100, always on | `drp-staging-frontend`, port 3101, **on demand** |
| Reachable at | `research.agribizframework.com` (Nginx + TLS) | `127.0.0.1` only — no DNS, no Nginx block, no public surface |
| Data | Real registers | Production's shape and volume, every identifying value replaced |

**It is a database first and a web stack second.** This VPS has ~956MB of RAM shared with
the sibling ABI project and uses swap at rest; a permanently-running second stack would
squeeze the production study system for an environment used occasionally. The risk staging
actually mitigates — a bad migration against real data — needs only the database. The web
units are installed but deliberately `static` (not enabled):

```bash
sudo bash /srv/agribiz-drp/deploy/staging-refresh.sh   # rebuild + scrub + rehearse migrations
sudo systemctl start drp-staging-backend drp-staging-frontend
ssh -L 8101:127.0.0.1:8101 -L 3101:127.0.0.1:3101 <host>   # then browse localhost:3101
sudo systemctl stop  drp-staging-backend drp-staging-frontend
```

**Why staging holds scrubbed production data rather than synthetic data.** The rule that
staging carries no real Main-400 records still holds — but a migration rehearsal against
synthetic fixtures is much weaker. The field-width failures found during the register
import (`Respondent.phone`, `Organisation.district`, `StratumDefinition.code`,
`DocumentRecord.value_chain`) were exactly the kind of defect only real data reveals.
`staging-refresh.sh` therefore restores the latest production backup and replaces every
identifying value, keeping row counts, lengths and shapes.

The scrub covers the model fields *and the `metadata` JSONB blobs*, which is where identity
most easily survives: the importers preserved every source-register column losslessly, so
`kii_kiirecord.metadata` carries `organisation_name`, free-text verification notes and
evidence URLs about named individuals. Scrubbing only the obvious columns would have left
all of that exposed.

The scrub is **verified, not assumed** — the script re-queries afterwards and, if any
identifying value survived, drops the staging database rather than leave it sitting there.
That guard was tested by injecting a fake unscrubbed name and confirming it trips.

`SECURE_SSL_REDIRECT`, the secure-cookie flags and HSTS are environment-driven with secure
defaults; only `backend/.env.staging` opts out, because staging is reached over a plain-HTTP
tunnel. Verified after the change: production still reports `SECURE_SSL_REDIRECT=True`.

### How the RPO is actually met

`systemd/drp-backup.timer` runs `deploy/backup.sh` every four hours on the clock
(00:00, 04:00, … UTC), with `Persistent=true` so a run missed during an outage fires at
next boot rather than waiting for the next slot — the window after an outage is exactly
when a restore point matters most. `backup.sh` writes gzipped `pg_dump` output to
`/srv/agribiz-drp/backups/` and prunes beyond 14 days.

```bash
systemctl list-timers drp-backup.timer     # when it next runs
systemctl start drp-backup.service         # take one now
journalctl -u drp-backup.service -n 20     # what happened last time
```

`deploy.sh` also takes one before every migration, and **aborts the deploy if it fails** —
a deploy with no restore point defeats the purpose of taking one. `SKIP_BACKUP=1` is the
deliberate override.

> **Why this is spelled out.** Until 2026-09-13 the deploy-time backup was gated on
> `[[ -x deploy/backup.sh ]]`; the executable bit is not preserved by the code-transfer
> route, so the step silently degraded to a one-line warning and no backup was taken for
> four consecutive deploys. The newest restore point at that moment predated the register
> import — 18K against a real database of 121K. A scheduled timer, a hard failure on
> error, and a documented way to check both are the response. **Verify a backup by its
> contents, not its existence:** `gunzip -c <file> | grep -c "^COPY public.sampling_organisation"`
> and count rows, as recorded in `28_DEFINITION_OF_DONE.md`.

Implementation: automated PostgreSQL backups no less frequently than every 4 hours
during Phases 1–3 (continuous WAL archiving / point-in-time recovery via the managed
database, or a scripted `pg_dump` cron matching the interval if self-managed), stored
off the application server, with a documented and **tested** restore procedure in
`backend/README.md` — untested backups do not count. A restore drill is an explicit
Phase 5 item in `27_AGENT_EXECUTION_PLAN.md` and an item in `28_DEFINITION_OF_DONE.md`,
not assumed to work.

## Rollout checklist for go-live

1. Confirm HTTPS is valid for `research.agribizframework.com`.
2. Confirm the staging rehearsal (synthetic cases only) has passed every item in
   `28_DEFINITION_OF_DONE.md`'s go-live checklist.
3. ~~Confirm the POTRAZ/data-protection position~~ — resolved 2026-09-12, see
   `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
4. Confirm the backup/restore drill has been run and passed against the RPO/RTO targets
   above.
5. Confirm the WhatsApp Business Platform templates are Meta-approved
   (`12_CONTACT_CRM_AND_MESSAGING.md`).
6. Confirm reserve locks and the de-identified export are verified against synthetic
   data one final time in production before the first real invitation.

## Offsite backups (Google Drive, encrypted) — added 2026-09-14

Every successful `drp-backup.service` run triggers `drp-offsite-backup.service`
(`OnSuccess=` drop-in), which copies the newest database dump and payload-file archive to
Google Drive through an rclone **crypt** remote: files are encrypted on the server, with
file names scrambled, so Google holds only ciphertext. Drive copies are kept 90 days
(`DRP_OFFSITE_RETENTION_DAYS`). Each upload is verified by size through the decryption
layer; a failed upload fails its own unit (`systemctl --failed`), never the local backup.

- **Setup (once, from your own computer):**
  `ssh -t -L 53682:127.0.0.1:53682 agribizframework 'sudo bash /srv/agribiz-drp/deploy/configure-offsite-backup.sh'`
  — open the printed link, sign in to the Google account that should hold the backups,
  allow. Scope is `drive.file`: the server can see only the files it created. The script
  then uploads, downloads back, decrypts and checks the dump before installing the timer
  hook.
- **The key.** `/etc/drp/offsite-backup-key.txt` holds the crypt password and salt in
  plain text. Copy both lines into a password manager; if the server is lost the Drive
  copies are unreadable without them.
- **Tested** 2026-09-14 on production with a local folder standing in for Drive: upload,
  scrambled names at rest, byte-identical restore (42 tables), and the not-yet-configured
  path exiting cleanly.

### Restoring from Google Drive on a new server

```bash
sudo dnf install -y rclone
rclone config create gdrive drive scope=drive.file          # sign in to the same Google account
rclone config create drp-offsite crypt remote=gdrive:ABF-FST-DRP-backups \
  filename_encryption=standard directory_name_encryption=true \
  password='<password from the key>' password2='<password2 from the key>' --obscure
rclone lsl drp-offsite:                                     # pick the newest drp-*.sql.gz
rclone copy drp-offsite:drp-YYYYMMDD-HHMMSS.sql.gz .
rclone copy drp-offsite:drp-files-YYYYMMDD-HHMMSS.tar.gz .
sudo -u postgres createdb drp_prod
gunzip -c drp-YYYYMMDD-HHMMSS.sql.gz | sudo -u postgres psql drp_prod
sudo tar xzf drp-files-YYYYMMDD-HHMMSS.tar.gz -C /srv/agribiz-drp/backend   # restores private_data/
```
