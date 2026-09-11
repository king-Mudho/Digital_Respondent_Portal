# Deployment — research.agribizframework.com

Full walkthrough for the DRP production deployment. See also `docs/23_DEPLOYMENT_
ARCHITECTURE.md` (the design) and the sibling ABI project's `docs/PRODUCTION_
ARCHITECTURE.md` (host-level lessons that apply unchanged here, since this shares
that project's VPS).

## Server

Same VPS as the sibling ABI project (`agribusiness-bankability/docs/DEPLOYMENT.md`
has the full server details — IP `66.29.139.201`, AlmaLinux 9, Contabo VPS Spark,
SSH key only). DRP adds nothing new to the OS-level access story.

**Resource note**: this VPS has only ~956MB RAM total and now runs two full
application stacks (ABI + DRP). Confirmed workable with DRP tuned down (1 Gunicorn
worker instead of 2, Celery `--pool=solo --concurrency=1`) but genuinely tight —
observed ~260-360MB "available" under normal load. If a third app is ever added
here, or DRP's traffic grows materially, resize the VPS or move one app off it.

## Domain

`research.agribizframework.com` — a subdomain of the ABI production host, per
`docs/20_EMBEDDING_WITH_ABI.md`: same VPS/Nginx instance for cost containment, but a
separate application, separate database, no navigational link either direction.

DNS: `A research.agribizframework.com -> 66.29.139.201`, managed by the user via
Namecheap (already configured and propagated as of this deployment).

## Application deployment

Directory layout on the server (parallel to, and independent of, `/srv/agribiz/`):

```
/srv/agribiz-drp/
├── backend/            # this repo's backend/, plus venv/, staticfiles/, media/, .env
├── frontend/
│   ├── (this repo's frontend/ source, plus .env — build happens here)
│   ├── releases/<timestamp>/
│   └── current -> releases/<timestamp>/
├── deploy/
├── nginx/
├── systemd/
├── logs/
└── backups/
```

Runs as its own system user (`agribiz-drp`, no login shell) -- **with a real home
directory** (`/home/agribiz-drp`), unlike a bare `--no-create-home` user: `npm ci`
needs a writable `HOME` for its cache. Found the hard way during this deployment's
first attempt (`EACCES: mkdir '/home/agribiz-drp'`) — `deploy/setup-server.sh` now
creates it explicitly.

Ports: backend on `127.0.0.1:8100`, frontend on `127.0.0.1:3100` — deliberately
different from ABI's `8000`/`3000` so the two apps' upstreams can never collide on
the same loopback interface.

### Getting the code onto the server

This deployment used `git archive HEAD | gzip`, scp'd to the server and extracted —
simpler than a full clone for a repo without a pushed remote yet. Once a remote
exists, `git clone`/`git pull` is the more usual path (see the sibling ABI project's
own docs for that option).

**Line-ending bug found here**: `git archive` on a Windows workstation with
`core.autocrlf=true` converts LF to CRLF when producing the archive, which breaks a
shell script's shebang line on the Linux target (`deploy.sh: line 16: $'\r':
command not found`). Fixed at the source with a `.gitattributes` file (`eol=lf` for
`.sh`/`.service`/`.conf`/`.py`/`.ts`/etc.), not by patching the extracted files —
anyone re-archiving from this repo on any OS now gets LF-only output.

### First deploy sequence

```bash
# 1. Provision (idempotent)
sudo bash /srv/agribiz-drp/deploy/setup-server.sh

# 2. Get the code onto the server (git archive + scp, or clone once a remote exists)

# 3. Fill in real secrets
sudo -u agribiz-drp cp deploy/env-templates/backend.env.production  /srv/agribiz-drp/backend/.env
sudo -u agribiz-drp cp deploy/env-templates/frontend.env.production /srv/agribiz-drp/frontend/.env
sudo chmod 600 /srv/agribiz-drp/backend/.env /srv/agribiz-drp/frontend/.env
# generate with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# 4. Deploy
sudo bash /srv/agribiz-drp/deploy/deploy.sh

# 5. First-time SSL (after DNS has propagated)
sudo dnf -y install certbot python3-certbot-nginx   # already present -- shared with ABI
sudo certbot --nginx -d research.agribizframework.com --redirect
```

## Environment variables

See `docs/24_ENVIRONMENT_CONFIGURATION.md` and `deploy/env-templates/*.env.production`.
Every secret (`DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`, the database password,
`KOBO_WEBHOOK_SHARED_SECRET`) was generated fresh for this deployment.

**`KOBO_API_TOKEN`, `KOBO_ASSET_UID`, `WHATSAPP_API_TOKEN` etc. are blank** — no
KoboToolbox account or WhatsApp Business Platform account has been provisioned yet
(`docs/27_AGENT_EXECUTION_PLAN.md` "Open questions"). The app runs correctly with
these blank; it just can't actually reach Kobo or WhatsApp until the PI/sponsor
provisions those accounts and the values are filled in (no redeploy needed — just
edit `.env` and restart the affected service).

## Database

`drp_prod`, role `drp_user` (login only, not a superuser), password auth over
`scram-sha-256` (matches the existing PostgreSQL 16 install's auth config — shared
with ABI's `agribiz_prod`, but a completely separate database, no cross-database FKs).

```bash
cd /srv/agribiz-drp/backend
sudo -u agribiz-drp env HOME=/home/agribiz-drp DJANGO_SETTINGS_MODULE=config.settings.prod \
    venv/bin/python manage.py migrate --noinput
```

**No seed data in production.** Unlike ABI's demo enterprises (deliberately kept
for the public `/demo` page), DRP's `seed_drp_dev` command creates only clearly-
synthetic test fixtures (`E2E Test Farming Trust`, etc.) — these were used once
during this deployment for a live staging rehearsal (see "Staging rehearsal" below)
and then deliberately deleted. **Production must stay genuinely empty until the PI
approves the first real Main-400 import** (`docs/28_DEFINITION_OF_DONE.md`,
`AGENTS.md` ground rule 1's Phase 11 gate).

## Nginx

Config: `nginx/research.agribizframework.conf`, installed to `/etc/nginx/conf.d/
research.agribizframework.conf` — a completely separate file and server block from
ABI's own `agribizframework.conf`. Same "let Certbot own the `:443` block" rule as
ABI (see that project's `docs/PRODUCTION_ARCHITECTURE.md` "The 127.0.0.1 lesson"):
this file has one `:80` block; `certbot --nginx --redirect` added the `:443` block,
certificate paths and redirect on top of it. Do not hand-write a `:443` block here
either.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## SSL

```bash
sudo certbot --nginx -d research.agribizframework.com --redirect
```

Verify:
```bash
curl --resolve research.agribizframework.com:443:127.0.0.1 https://research.agribizframework.com/ -I
sudo certbot certificates   # should list both agribizframework.com and research.agribizframework.com
```

Renewal: the same system-wide `certbot-renew.timer` that already covered ABI's
certificate now covers both — confirmed via `certbot renew --dry-run`, which
reported "all simulated renewals succeeded" for both domains.

## Services

| systemd unit | What | Logs |
|---|---|---|
| `drp-backend` | Django API via Gunicorn (`127.0.0.1:8100`) | `journalctl -u drp-backend` |
| `drp-frontend` | Next.js standalone SSR (`127.0.0.1:3100`) | `journalctl -u drp-frontend` |
| `drp-celery-worker` | Kobo reconciliation + reminder dispatch (`--pool=solo`) | `journalctl -u drp-celery-worker` |
| `drp-celery-beat` | Scheduler for the above (DB-driven schedule) | `journalctl -u drp-celery-beat` |
| `nginx` | Reverse proxy, TLS termination (shared with ABI) | `/var/log/nginx/drp-{access,error}.log` |
| `postgresql` | Database (shared instance, separate `drp_prod` database) | `journalctl -u postgresql` |
| `redis` | Celery broker (new for this deployment — ABI doesn't use it) | `journalctl -u redis` |

### Restart commands

```bash
sudo systemctl restart drp-backend drp-frontend drp-celery-worker drp-celery-beat
sudo systemctl reload  nginx     # config change, no dropped connections
```

## Staging rehearsal (this deployment)

No separate staging box exists (the ~956MB RAM budget doesn't comfortably support a
third full stack) — the rehearsal ran directly against what becomes production,
using `seed_drp_dev`'s synthetic fixtures, then explicitly deleted before handing
this over:

1. Seeded synthetic organisations/sample cases/an invitation token.
2. Verified live over the real HTTPS domain: invitation validation → organisation
   confirmation → eligibility gate (both screens render correctly, real API calls).
3. Verified admin login (JWT) works over HTTPS.
4. Ran the backup/restore drill for real: `backup.sh`, restored into a scratch
   database (`drp_restore_test`), confirmed the seeded rows were actually present,
   dropped the scratch database.
5. Deleted every synthetic record and the temporary `e2e_admin` account. Confirmed
   `Organisation.objects.count() == 0` and `User.objects.count() == 0` before
   finishing.

**Not run**: the full 15-item go-live checklist in `docs/28_DEFINITION_OF_DONE.md`
item-by-item against this live deployment (most items are already covered by the
Phase 9 automated test suite, which exercises the identical code against a local
dev database — not re-run one-by-one here). That checklist, plus the POTRAZ/DPO
determination and WhatsApp Meta template approval, are Phase 11's explicit gate —
"the PI, not the agent, makes the final go-live call"
(`docs/28_DEFINITION_OF_DONE.md`).

## Backup & restore

```bash
sudo bash /srv/agribiz-drp/deploy/backup.sh
sudo bash /srv/agribiz-drp/deploy/rollback.sh --restore-db /srv/agribiz-drp/backups/drp-<timestamp>.sql.gz
```

**This procedure has been verified**: a real backup taken during this deployment
was restored into a scratch database and its data (2 organisations, 2 sample cases,
1 invitation token) confirmed present. Re-run this verification after any schema
change that isn't a pure additive migration.

docs/23's RPO target (≤4 hours during active fieldwork) needs `backup.sh` on a
cron/systemd-timer at that cadence during Phases 1-3 of fieldwork — not wired up
automatically here, since the right cadence depends on the fieldwork calendar, not
a fixed constant.

## Troubleshooting

Same failure modes and fixes as the sibling ABI project's own `docs/DEPLOYMENT.md`
§ Troubleshooting apply here unchanged (502s, the 127.0.0.1/Certbot catch-all
gotcha, CSRF/SECURE_PROXY_SSL_HEADER, OOM during `npm run build`) — substitute
`drp-backend`/`drp-frontend` for `agribiz-backend`/`agribiz-frontend` and
`research.agribizframework.com` for `agribizframework.com`.

**`npm ci` fails with `EACCES: mkdir '/home/<user>'`.** The app's system user has no
real home directory. Fix: `mkdir -p /home/<user> && chown <user>:<user> /home/<user>
&& chmod 700 /home/<user>`. `setup-server.sh` does this for `agribiz-drp` already;
only relevant if the user was created some other way.

**Celery worker won't start / tasks never run.** Check Redis is up
(`systemctl status redis`, `redis-cli ping`) and `CELERY_BROKER_URL` in `.env`
points at it. `journalctl -u drp-celery-worker -n 50` first.
