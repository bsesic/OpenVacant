# Deployment

Production deployment for OpenVacant. Two supported strategies — pick one.

Whichever you pick, one rule is not negotiable: **the media root is never served
directly by the web server.** It holds expert reports, letters to owners and
unreleased photographs beside released ones, so a public `/media/` location
would publish them. Files are delivered by views that authorise the caller and
then hand the file to NGINX through an internal location. Both NGINX
configurations here are already set up that way.

## What runs

| Component | Why |
|-----------|-----|
| PostgreSQL **with PostGIS** | Geometry is a first-class field. Not optional. |
| Redis | Cache, sessions, rate-limit counters, and the Celery broker. |
| Gunicorn (WSGI) | The application. Templates-first, so WSGI is enough. |
| Daphne (ASGI) | Optional alternative, only if you add WebSocket features. |
| Celery worker | Geodata imports, spatial context, statistics, retention. |
| Celery beat | Nightly snapshot and the retention run. Exactly one. |
| Flower | Optional Celery monitoring, bound to localhost. |
| NGINX | TLS, static files, rate limits, protected file delivery. |

## Strategy A — host deployment (systemd)

Layout on the server: `/opt/openvacant` (repo) + `/opt/openvacant/venv`.

1. Create the `openvacant` system user, `/var/log/openvacant` and
   `/var/lib/openvacant` (the beat schedule lives there), all owned by it.
2. Install PostgreSQL and PostGIS, then create the database and the extension:

   ```bash
   sudo -u postgres createuser openvacant --pwprompt
   sudo -u postgres createdb openvacant --owner openvacant
   sudo -u postgres psql -d openvacant -c 'CREATE EXTENSION IF NOT EXISTS postgis;'
   ```

3. Install the geospatial libraries the application needs:

   ```bash
   sudo apt-get install binutils libproj-dev gdal-bin libgeos-c1v5
   ```

4. Clone the repository to `/opt/openvacant`, create the virtualenv, and copy
   `.env.production.example` to `backend/.env`.
5. Install the systemd units from `deploy/systemd/` and enable
   `openvacant-gunicorn`, `openvacant-celery` and `openvacant-celerybeat`.
6. Install `deploy/nginx/openvacant.conf` into `/etc/nginx/sites-available/`,
   and `deploy/nginx/snippets/openvacant-proxy.conf` into
   `/etc/nginx/snippets/`. Adjust the domain and paths, then symlink into
   `sites-enabled` and reload.
7. Install log rotation: copy `deploy/logrotate/openvacant` to
   `/etc/logrotate.d/openvacant` (root-owned, `0644`). Test with
   `logrotate -d /etc/logrotate.d/openvacant`.
8. Deploy: `sudo -u openvacant deploy/deploy.sh`.

### The deploy script

`deploy/deploy.sh` deploys **the current release**: the latest annotated tag,
unless `DEPLOY_REF` says otherwise. It fetches, checks out, installs
dependencies, builds the frontend assets, runs Django's deploy checklist,
verifies that PostGIS is present, migrates, collects static files, compiles
translations, clears expired sessions, restarts the services and checks
`/readyz`.

```bash
sudo -u openvacant deploy/deploy.sh                    # current release
DEPLOY_REF=v1.2.0 sudo -u openvacant deploy/deploy.sh  # a specific release
```

It restarts the web process, the worker **and** the scheduler, because a release
that changes a task or the schedule leaves them running the previous code
otherwise.

## Strategy B — Docker Compose

```bash
cp deploy/.env.production.example deploy/.env.production   # then edit it
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production up -d
```

Brings up PostGIS, Redis, the application, a worker, the scheduler and NGINX.
Postgres and Redis are not published to the host. TLS is expected from a reverse
proxy in front of the stack; the bundled NGINX trusts `X-Forwarded-Proto` from
it.

Migrations and `collectstatic` run in the web service's start command, so a
`docker compose up -d` after pulling a new image is a complete deploy.

## Environment

See [`.env.production.example`](.env.production.example) for the full list. The
ones worth checking before going live:

| Variable | Note |
|----------|------|
| `DJANGO_SECRET_KEY` | Long and random. Rotating it invalidates all sessions. |
| `DJANGO_ALLOWED_HOSTS` | Without the real host, every request is refused. |
| `DATABASE_URL` | `postgis://` scheme. The extension must exist. |
| `USE_X_ACCEL_REDIRECT` | Keep `True` behind NGINX, or Python streams every file. |
| `GEOCODER_USER_AGENT` | Must carry a real contact address — the upstream service requires it. |
| `SECURE_SSL_REDIRECT` | Turn off only if the proxy in front already redirects. |
| `AWS_QUERYSTRING_AUTH` | Keep `True` when using S3; a public bucket defeats the authorisation layer. |

## Background work

The worker and the scheduler are not optional extras. Without them, geodata
context is never recomputed, no statistics snapshots accumulate — so the time
series stays empty — and the retention rules never delete anything, which is a
data protection problem rather than an inconvenience.

**Flower** monitors them via `openvacant-flower.service`, bound to
`127.0.0.1:5555`. Reach it through an SSH tunnel: it shows task arguments, which
can include record references.

## Backups

`deploy/scripts/backup.sh` writes a timestamped snapshot of the database, the
media root and the (optionally gpg-encrypted) `.env` under
`/var/backups/openvacant/<timestamp>/`, prunes by age, and pushes offsite with
restic when configured. Schedule it with
`deploy/systemd/openvacant-backup.{service,timer}` (daily).

Restoring needs the extension in place before the dump goes back in:

```bash
createdb openvacant && psql -d openvacant -c 'CREATE EXTENSION postgis;'
pg_restore -h <host> -U <user> -d openvacant -j 4 /var/backups/openvacant/<TS>/db.dump
tar -xzf /var/backups/openvacant/<TS>/media.tar.gz -C /opt/openvacant/backend/
```

Full steps, including rollback, are in
[`../docs/deployment-runbook.md`](../docs/deployment-runbook.md).

## Several municipalities on one server

Each municipality runs its own instance: its own database, its own media root,
its own domain. Postgres and Redis can be shared (separate databases and Redis
database numbers), but the application, worker and scheduler are per instance —
that separation is what municipal data sovereignty means in practice.
