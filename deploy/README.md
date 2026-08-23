# Deployment

Production deployment for the OpenVacant. Two supported strategies — pick one,
do not mix them on the same host.

## Release model

`main` is the deployable branch. Releases are annotated git tags (e.g. `v1.2.3`).
`deploy.sh` deploys the **current release** (the latest tag) by default; override with
`DEPLOY_REF`.

## Frontend assets (Vite)

Templates load CSS/JS through `django-vite`. The assets must be built before
`collectstatic`:

```bash
cd frontend && npm ci && npm run build   # outputs to backend/static/dist/
```

`deploy.sh` runs this automatically when `npm` and a `frontend/` directory are
present. **Strategy B (Docker):** the bundled `web` image is Python-only, so build
the assets on a machine with Node first (or add a Node build stage); the `static_data`
volume then serves them via NGINX.

## WSGI vs. ASGI — important

The default app server is **Gunicorn (WSGI)**, which is correct for the templates-first
phase (no WebSockets). Switch to **Daphne (ASGI)** *only* if you add Channels/WebSockets,
and then run **either** gunicorn **or** daphne for the app — never both for the same
routes. NGINX routes `/ws/` to the ASGI server; everything else can stay on WSGI if you
split them, but the simple path is one server for everything.

## Strategy A — systemd + host NGINX (recommended for a single server)

Layout on the server: `/opt/openvacant` (repo) + `/opt/openvacant/venv`.

1. Install the systemd units from `deploy/systemd/` into `/etc/systemd/system/`
   (`openvacant-gunicorn.service`, optionally `openvacant-celery.service`, `openvacant-celerybeat.service`).
2. Copy `deploy/.env.production.example` to `backend/.env` and fill it in.
3. Install `deploy/nginx/openvacant.conf` into `/etc/nginx/sites-available/`,
   adjust the domain and paths, symlink into `sites-enabled`, obtain TLS via certbot.
4. Create `/var/log/openvacant` (owned by the `openvacant` user) and the `openvacant` system user.
5. Install log rotation: copy `deploy/logrotate/openvacant` to
   `/etc/logrotate.d/openvacant` (root-owned, `0644`); adjust the path and the
   `su`/`create` user to match. Test with `logrotate -d /etc/logrotate.d/openvacant`.
6. Deploy: `sudo -u openvacant deploy/deploy.sh`.

`deploy.sh` fetches the release, installs deps, builds frontend assets, runs
`check --deploy`, migrates, collects static, compiles messages, clears sessions,
restarts services, and verifies `/readyz` (with coloured step logging and sanity checks).

## Strategy B — full Docker stack

Self-contained: Postgres + Redis + Gunicorn + NGINX in containers.

```bash
cp deploy/.env.production.example backend/.env   # then edit
docker compose -f deploy/docker-compose.prod.yml --env-file backend/.env up -d --build
```

Uses `deploy/nginx/openvacant.docker.conf` (proxies to the `web` service, serves
static/media from shared volumes). Mount your TLS certs at `/etc/letsencrypt`.

## Continuous deployment (GitHub Actions → GHCR → SSH)

`.github/workflows/deploy.yml` automates Strategy B on a release tag (`vX.Y.Z`) or a
manual run:

1. **Build & push** the backend image to `ghcr.io/<owner>/<repo>-backend` (tagged with
   the version, the commit SHA, and `latest`), using GHA build cache.
2. **Deploy over SSH**: connects to the server, checks out the release tag (for the
   compose file), and runs `docker compose -f deploy/docker-compose.prod.yml pull web &&
   up -d`. The `web` service defaults to the `:latest` GHCR image (just published), and
   migrations + collectstatic run from its start command.

Required repo **secrets** (Settings → Secrets and variables → Actions):

| Secret | Purpose |
|--------|---------|
| `DEPLOY_HOST` | server hostname/IP |
| `DEPLOY_USER` | SSH user (member of the `docker` group) |
| `DEPLOY_SSH_KEY` | private key for that user |
| `DEPLOY_PORT` | SSH port (optional, default 22) |
| `DEPLOY_PATH` | repo checkout on the server (optional, default `/opt/openvacant`) |

The server needs the repo checked out at `DEPLOY_PATH` (for the compose file), Docker +
the compose plugin, `backend/.env`, and the GHCR image must be pullable (public package
or `docker login ghcr.io` configured). To cut a release: `git tag v0.1.0 && git push --tags`.

## Background jobs (Celery + Flower)

Celery is wired into `core` (broker/result backend = Redis). Run the worker and
scheduler from `deploy/systemd/` (`openvacant-celery.service`, `openvacant-celerybeat.service`).
**Flower** monitors them via `openvacant-flower.service` (bound to `127.0.0.1:5555`,
basic-auth via `FLOWER_USER`/`FLOWER_PASSWORD` — proxy it behind NGINX with TLS).
Locally: `celery -A core worker -l info` and `celery -A core flower`.

## Shared services across projects

For multiple projects on one server, run **one** Postgres and **one** Redis as shared
services (a database and a Redis DB number per project) and give each project its own app
service + NGINX site. See `docs/IMPLEMENTATION_PLAN.md` §4 Phase 10.

## Backups

`deploy/scripts/backup.sh` snapshots the database (`pg_dump` custom format), media, and
the (optionally gpg-encrypted) `.env` under `/var/backups/openvacant/<timestamp>/`, prunes by
`RETENTION_DAYS`, and pushes offsite with **restic** when `RESTIC_REPOSITORY` is set.
Schedule it via `deploy/systemd/openvacant-backup.{service,timer}` (daily). Restore steps are in
the script header and the [deployment runbook](../docs/deployment-runbook.md).
