# ABF-FST Digital Respondent Portal — backend

Django 5 + Django REST Framework API for the research-operations portal supporting the
ABF-FST study. Not a questionnaire engine (KoboToolbox is) and not a bankability-scoring
tool (see `docs/25_FUTURE_ABI_ENGINE_PHASE4.md`). See the repository root `AGENTS.md` and
`docs/` for the full specification.

## Local development

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env               # then edit DATABASE_URL, DJANGO_SETTINGS_MODULE=config.settings.dev, etc.
python manage.py migrate
python manage.py seed_drp_dev      # dev fixtures: test strata, synthetic sample cases (Phase 2+)
python manage.py runserver
```

A local PostgreSQL instance is required (see `docs/04_TECH_STACK.md`) — a separate
database from the sibling ABI project's `abi_dev`:

```sql
CREATE ROLE drp_user WITH LOGIN PASSWORD 'devpassword';
CREATE DATABASE drp_dev OWNER drp_user;
```

Celery/Redis (`docs/04_TECH_STACK.md`) power the Kobo reconciliation and reminder-queue
jobs only. In dev, `CELERY_TASK_ALWAYS_EAGER=True` (the `.env` default) runs those tasks
synchronously in-process so a local Redis broker isn't required just to exercise the
logic manually. Set it to `False` and run Redis locally to test the actual Celery Beat
schedule end to end.

## Tests

```bash
pytest
```

## Deployment

See `docs/23_DEPLOYMENT_ARCHITECTURE.md` for the full topology and the repository root
`nginx/`/`systemd/`/`deploy/` directories (added in the deployment-prep phase) for the
concrete Nginx config, systemd units and backup/restore scripts — same pattern as the
sibling ABI project's `agribusiness-bankability/` deployment, on the same VPS.

## Environment variables

See `.env.example` and `docs/24_ENVIRONMENT_CONFIGURATION.md`. Never commit a real
`.env`.
