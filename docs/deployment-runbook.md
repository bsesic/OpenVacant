# Deployment runbook

Operational procedures for an OpenVacant instance. Configuration reference lives
in [`../deploy/README.md`](../deploy/README.md).

## First installation

1. **System packages**

   ```bash
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-venv nginx postgresql postgresql-16-postgis-3 \
                        redis-server binutils libproj-dev gdal-bin libgeos-c1v5 gettext
   ```

2. **User and directories**

   ```bash
   sudo useradd --system --create-home --shell /bin/bash openvacant
   sudo mkdir -p /var/log/openvacant /var/lib/openvacant /opt/openvacant
   sudo chown openvacant:openvacant /var/log/openvacant /var/lib/openvacant /opt/openvacant
   ```

3. **Database**

   ```bash
   sudo -u postgres createuser openvacant --pwprompt
   sudo -u postgres createdb openvacant --owner openvacant
   sudo -u postgres psql -d openvacant -c 'CREATE EXTENSION IF NOT EXISTS postgis;'
   ```

   The extension is a one-off manual step: the application user should not hold
   the rights needed to create extensions.

4. **Code and environment**

   ```bash
   sudo -u openvacant git clone https://github.com/bsesic/OpenVacant.git /opt/openvacant
   cd /opt/openvacant
   sudo -u openvacant python3.11 -m venv venv
   sudo -u openvacant venv/bin/pip install -r backend/requirements.txt
   sudo -u openvacant cp deploy/.env.production.example backend/.env
   sudo -u openvacant chmod 600 backend/.env
   # then edit backend/.env
   ```

5. **Services and web server** — install the units from `deploy/systemd/`, the
   site from `deploy/nginx/`, and the snippet into `/etc/nginx/snippets/`.
   Enable `openvacant-gunicorn`, `openvacant-celery`, `openvacant-celerybeat`
   and the backup timer.

6. **First deploy**

   ```bash
   sudo -u openvacant deploy/deploy.sh
   ```

7. **Onboard the municipality**

   ```bash
   cd /opt/openvacant/backend
   sudo -u openvacant ../venv/bin/python manage.py createsuperuser
   ```

   Then create the tenant and its municipality profile in `/admin/`, or run
   `manage.py seed_demo` for a demonstration instance. Everything else —
   branding, districts, legal texts, active modules — is configured through the
   administration UI.

## Deploying a release

Always deploy from `main`. A release is a merge of `development` into `main` plus
an annotated tag.

```bash
# On a workstation
git checkout main && git merge --no-ff development
git tag -a v1.2.0 -m "Release 1.2.0" && git push origin main --tags

# On the server
sudo -u openvacant /opt/openvacant/deploy/deploy.sh
```

The script deploys the latest annotated tag by default. Watch for the PostGIS
check and the closing health check; it exits non-zero if either fails.

## Rolling back

```bash
DEPLOY_REF=v1.1.0 sudo -u openvacant /opt/openvacant/deploy/deploy.sh
```

Code rolls back cleanly. **Migrations do not.** Before rolling back across a
release that migrated, check what it did:

```bash
sudo -u openvacant venv/bin/python backend/manage.py showmigrations --plan | tail -30
```

A migration that only added a column or a table is harmless to leave in place —
the previous code ignores it. A migration that dropped or renamed something has
to be reversed deliberately, or restored from the backup taken before the
deploy. This is why the backup timer runs before the usual deployment window.

## Health checks

| Endpoint | Meaning |
|----------|---------|
| `/healthz` | The process is up and answering. |
| `/readyz` | The database is reachable. Use this for load balancers. |

```bash
systemctl status openvacant-gunicorn openvacant-celery openvacant-celerybeat
journalctl -u openvacant-gunicorn -n 100 --no-pager
tail -f /var/log/openvacant/error.log
```

## Recurring jobs

Both run through Celery beat. If beat is not running, neither happens.

| Job | When | Consequence if it stops |
|-----|------|-------------------------|
| Key figure snapshot | 00:20 daily | The time series stops growing, and past days cannot be reconstructed. |
| Retention rules | 03:00 daily | Data that should have been deleted is kept — a data protection problem. |

Run either by hand if needed:

```bash
cd /opt/openvacant/backend
sudo -u openvacant ../venv/bin/python manage.py snapshot_statistics
sudo -u openvacant ../venv/bin/python manage.py apply_retention --dry-run
sudo -u openvacant ../venv/bin/python manage.py apply_retention
```

## Importing geodata

Layers come as files from state and municipal portals. A repeated import under
the same key **replaces** the layer, which is deliberate: a partially updated
layer would give the wrong answer for every object in the missing part.

```bash
cd /opt/openvacant/backend
sudo -u openvacant ../venv/bin/python manage.py import_geojson \
    /srv/geodata/sanierungsgebiete.geojson \
    --municipality 14523250 \
    --name "Redevelopment areas" \
    --category redevelopment \
    --source "Saxony geodata portal" \
    --refresh-context
```

After importing or deactivating a layer, the context flags on existing records
are stale until recomputed:

```bash
sudo -u openvacant ../venv/bin/python manage.py refresh_geo_context --municipality 14523250
```

## Backups and restore

Daily via `openvacant-backup.timer` into `/var/backups/openvacant/<timestamp>/`
(database dump, media archive, encrypted `.env`), pushed offsite by restic when
`RESTIC_REPOSITORY` is set. For `.env` encryption, put a passphrase in
`/etc/openvacant/backup.passphrase`.

Restore:

```bash
sudo systemctl stop openvacant-gunicorn openvacant-celery openvacant-celerybeat
sudo -u postgres dropdb openvacant
sudo -u postgres createdb openvacant --owner openvacant
sudo -u postgres psql -d openvacant -c 'CREATE EXTENSION postgis;'
sudo -u postgres pg_restore -d openvacant -j 4 /var/backups/openvacant/<TS>/db.dump
sudo -u openvacant tar -xzf /var/backups/openvacant/<TS>/media.tar.gz -C /opt/openvacant/backend/
gpg --decrypt --passphrase-file /etc/openvacant/backup.passphrase \
    /var/backups/openvacant/<TS>/env.gpg > /opt/openvacant/backend/.env
sudo systemctl start openvacant-gunicorn openvacant-celery openvacant-celerybeat
```

The extension has to exist before the dump goes in, or every geometry column
fails to restore.

## Certificates

```bash
sudo certbot certonly --webroot -w /var/www/certbot -d example.com -d www.example.com
sudo systemctl reload nginx
```

The HTTP server block keeps `/.well-known/acme-challenge/` on port 80 so
renewals work without touching the configuration.

## Rotating secrets

- **`DJANGO_SECRET_KEY`** — invalidates every session and every signed link.
  Announce it, then restart the web process.
- **API client keys** — rotate or revoke them in the administration UI under
  *API clients*. A rotated key stops working immediately.
- **Database password** — change it in Postgres and in `backend/.env`, then
  restart the web process, the worker and the scheduler.

## Incidents

**The site is down.** Check `systemctl status openvacant-gunicorn`, then
`/var/log/openvacant/error.log`. `/readyz` returning 503 points at the database
rather than the application.

**Reports are not arriving.** Check that the municipality has a boundary
imported and that anonymous reporting is enabled for it; both silently reduce
what a visitor can do. Then check the rate limits in the NGINX error log.

**A file is not downloading.** Files are served through the application. A 403
is the authorisation layer working as intended; a 404 from NGINX means the
`/protected/` alias does not match the media root.

**Suspected data disclosure.** The access log in the administration UI records
who saw personal or internal data. It is scoped per municipality and readable by
managers.
