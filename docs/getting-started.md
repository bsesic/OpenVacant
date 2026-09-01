# Getting started

Local development setup for OpenVacant.

## Requirements

- Python 3.11
- Node 20+ (frontend assets)
- PostgreSQL 16+ **with PostGIS 3.4+**
- Redis (cache and Celery broker)
- GEOS, GDAL and PROJ (GeoDjango)

Docker covers all of the infrastructure; only Python and Node need to be local.

## 1. Infrastructure

```bash
docker compose up -d db redis mailpit
```

This starts PostGIS on 5432, Redis on 6379 and Mailpit (SMTP 1025, UI
http://localhost:8025).

Prefer a local Postgres? Then create the database and enable the extension
yourself, and make sure PostGIS is available in `template1` as well so Django can
create the test database:

```bash
createdb openvacant
psql -d openvacant -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -d template1  -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

## 2. Backend

```bash
cd backend
python3.11 -m venv ../venv && source ../venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo          # Reichenbach demo data
python manage.py createsuperuser
python manage.py runserver
```

### macOS: GeoDjango cannot find GEOS or GDAL

GeoDjango locates the libraries automatically on Linux. On macOS, install them
and point Django at them in `backend/.env`:

```bash
brew install geos gdal
```

```dotenv
GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
```

Homebrew's PostGIS is built against a specific PostgreSQL version. If
`CREATE EXTENSION postgis` fails with a missing control file, the running server
is a different major version than the one PostGIS was built for — use the Docker
service instead, or run the matching `postgresql@NN` formula.

## 3. Frontend assets

```bash
cd frontend
npm install
npm run dev        # Vite dev server with HMR; django-vite picks it up when DEBUG=True
# npm run build    # production build into backend/static/dist/
```

## Where things are

| URL | What |
|-----|------|
| `/` | Public pages and the public map |
| `/reports/new/` | Citizen report form |
| `/admin/` | Django administration (Unfold theme) |
| `/api/docs/` | OpenAPI documentation |
| `/healthz`, `/readyz` | Liveness and readiness probes |

## Configuration

Everything optional degrades gracefully when unset. Per-project settings live in
`backend/.env`; see `.env.example` for the full list.

- **Maps** — `MAP_TILE_URL`, `MAP_DEFAULT_*`. A municipality can override the
  centre and zoom in its own settings.
- **Geocoding** — `GEOCODER_PROVIDER=nominatim|none`. The public Nominatim
  service requires a real contact address in `GEOCODER_USER_AGENT` and tolerates
  roughly one request per second; use your own instance for production volume.
- **Object storage** — `USE_S3=True` plus the `AWS_*` variables for
  S3-compatible storage of photos and documents.
- **Email** — point `EMAIL_*` at your relay.
- **Social login** — set `<PROVIDER>_CLIENT_ID` and `<PROVIDER>_SECRET`.
- **Analytics** — `ANALYTICS_PROVIDER=plausible|matomo`.
- **Citizen reporting** — `ANONYMOUS_REPORTS_ENABLED`, `REPORT_RATE_LIMIT`.

## Adding a domain app

Domain apps live in `backend/apps/` and are tenant-scoped:

```python
# apps/example/models.py
from organizations.models import OrganizationOwnedModel

class Example(OrganizationOwnedModel):
    name = models.CharField(max_length=200)
```

```python
# apps/example/views.py
from organizations.mixins import CurrentOrganizationRequiredMixin, OrgScopedQuerysetMixin

class ExampleListView(CurrentOrganizationRequiredMixin, OrgScopedQuerysetMixin, ListView):
    model = Example
```

Register it in `INSTALLED_APPS` as `apps.example`. Views that must be restricted
to the administration use the role mixins from `organizations.mixins`.

Note that a user without a membership is a citizen: `request.organization` is
`None` and the tenant mixins deny access. Citizen-facing views must not use them.

## Quality gates

```bash
cd backend
flake8 .
pytest
```

`pre-commit install` wires both as git hooks; CI runs them on every push and pull
request against `main` and `development`.

## Workflow

Create the issue first, branch from `development` (`feature/*`, `bugfix/*`), lint
and test, then open a pull request into `development`. Releases are cut by merging
`development` into `main` and tagging it. See the
[deployment runbook](deployment-runbook.md).
