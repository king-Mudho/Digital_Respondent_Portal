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
