# OpenVacant

A vacancy and potential register for municipalities. Citizens report vacancy,
the administration verifies it, and scattered observations become a defensible
basis for urban development.

> Detect vacancy. Understand potential. Involve owners and citizens.
> Make municipalities capable of acting. Develop the town together.

The reference implementation is a proof of concept for **Reichenbach im Vogtland**,
built so that any other municipality can run its own instance.

## What it does

- **Citizens** report suspected vacancy, building damage or hazards — with a map
  marker, photos and no account required.
- **The administration** verifies reports on site, keeps a full property record
  per object, and works through tasks with a traceable status history.
- **Geodata** puts every object in context: heritage protection, redevelopment,
  funding and urban restructuring areas.
- **Statistics** turn the register into key figures per district, property type
  and condition.
- **The API** is a first-class component with a strict separation between public
  data and internal professional data.

## Architecture

API-first, headless-capable, modular, open source and ready for federation. The
core is a modular Django monolith: simple to deploy today, separable later.

```
backend/          Django project
  core/           settings, URLs, Celery, health probes
  apps/           domain apps (properties, reports, inspections, gis, ...)
  users/ organizations/ billing/ ...   platform apps
frontend/         Vite asset pipeline (Bootstrap 5, progressive enhancement)
deploy/           NGINX, systemd units, production compose, deploy script
docs/             architecture, ADRs, runbooks
```

Stack: Django 5.1 · Django REST Framework · PostgreSQL + PostGIS · Redis + Celery ·
S3-compatible object storage · Docker · OpenAPI.

See [`docs/architecture.md`](docs/architecture.md) for the module map and
[`docs/adr/`](docs/adr/README.md) for the decisions behind it.

## Quickstart (local development)

Requires Docker (or a local PostGIS) and Node 20+.

```bash
# 1. Infrastructure: PostGIS, Redis, Mailpit
docker compose up -d db redis mailpit

# 2. Backend
cd backend
python -m venv ../venv && source ../venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # adjust if needed
python manage.py migrate
python manage.py seed_demo      # Reichenbach demo data
python manage.py createsuperuser
python manage.py runserver

# 3. Frontend assets (second terminal)
cd frontend
npm install
npm run dev
```

http://localhost:8000 · admin `/admin/` · API docs `/api/docs/` · Mailpit http://localhost:8025

On macOS, GeoDjango needs the Homebrew libraries — set `GEOS_LIBRARY_PATH` and
`GDAL_LIBRARY_PATH` in `backend/.env`. See [`docs/getting-started.md`](docs/getting-started.md).

## Quality gates

Run before every commit (also enforced by pre-commit and CI):

```bash
cd backend && flake8 . && pytest
```

## Branching

- `main` — releases, deployed to production.
- `development` — active development.
- `feature/*`, `bugfix/*` — branched off `development`.

## Deployment

Always deploy the current release from `main`. See
[`docs/deployment-runbook.md`](docs/deployment-runbook.md) and
[`deploy/README.md`](deploy/README.md).

## Data protection

Municipal data sovereignty and the GDPR are design constraints, not features:
role-based access, a hard split between public and internal fields, consent
records, audit logging, retention rules and revocable API access. Public API
responses never contain personal owner, user or administrative information.

## Licence

See [LICENSE](LICENSE).
