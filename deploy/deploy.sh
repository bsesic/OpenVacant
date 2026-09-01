#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# OpenVacant production deploy script
#
# Run on the server. Deploys the current release (latest annotated git tag by
# default; override with DEPLOY_REF=<tag|branch>). Pulls code, installs deps,
# builds frontend assets, runs Django's deploy checklist, migrates, collects
# static, compiles translations, clears sessions, restarts the systemd services
# and pings the health check.
#
# Expects: a virtualenv at $VENV_DIR, backend/.env on the server, the systemd
# units installed, and passwordless sudo for `systemctl restart` on those units.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration (override via environment) ─────────────────────────────────
PROJECT_DIR="${PROJECT_DIR:-/opt/openvacant}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_DIR/backend}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
PYTHON="${PYTHON:-$VENV_DIR/bin/python}"
PIP="${PIP:-$VENV_DIR/bin/pip}"
# All long-running services, not just the web process: a release that changes a
# Celery task or the beat schedule needs the worker and the scheduler restarted
# too, or they keep running the previous code.
SERVICES="${SERVICES:-openvacant-gunicorn openvacant-celery openvacant-celerybeat}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-https://example.com/readyz}"
HEALTHCHECK_TIMEOUT="${HEALTHCHECK_TIMEOUT:-15}"

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

# ── Sanity checks ────────────────────────────────────────────────────────────
cd "$PROJECT_DIR" || fail "PROJECT_DIR not found: $PROJECT_DIR"
[ -f "$BACKEND_DIR/manage.py" ]        || fail "manage.py not found in $BACKEND_DIR"
[ -f "$BACKEND_DIR/requirements.txt" ] || fail "requirements.txt not found in $BACKEND_DIR"
[ -x "$PYTHON" ]                       || fail "Python not executable at $PYTHON"

# ── Load .env ────────────────────────────────────────────────────────────────
if [ -f "$BACKEND_DIR/.env" ]; then
    log "Loading $BACKEND_DIR/.env"
    set -a
    # shellcheck disable=SC1091
    . "$BACKEND_DIR/.env"
    set +a
else
    warn "backend/.env not found — relying on existing environment variables"
fi

# ── 1. Fetch and check out the release ───────────────────────────────────────
git fetch --prune --tags origin
DEPLOY_REF="${DEPLOY_REF:-$(git describe --tags "$(git rev-list --tags --max-count=1)" 2>/dev/null || echo main)}"
log "1/9 Deploying ref: $DEPLOY_REF"
git checkout --force "$DEPLOY_REF"
if git show-ref --verify --quiet "refs/remotes/origin/$DEPLOY_REF"; then
    git reset --hard "origin/$DEPLOY_REF"
fi
export SENTRY_RELEASE="${SENTRY_RELEASE:-$(git rev-parse --short HEAD)}"
log "    HEAD $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"

# ── 2. Python dependencies ───────────────────────────────────────────────────
log "2/9 Installing Python requirements"
"$PIP" install --upgrade pip
"$PIP" install -r "$BACKEND_DIR/requirements.txt"

# ── 3. Frontend assets (Vite) ────────────────────────────────────────────────
if [ -d "$PROJECT_DIR/frontend" ] && command -v npm >/dev/null 2>&1; then
    log "3/9 Building frontend assets"
    (cd "$PROJECT_DIR/frontend" && npm ci && npm run build)
else
    warn "3/9 Skipping frontend build (no frontend/ or npm not found)"
fi

cd "$BACKEND_DIR"

# ── 4. Deploy checklist ──────────────────────────────────────────────────────
log "4/9 Running Django deploy checklist"
"$PYTHON" manage.py check --deploy

# PostGIS is required, and a missing extension shows up as an unhelpful error
# during migrate. Say so plainly instead.
log "    Verifying PostGIS"
if ! "$PYTHON" - <<'PYCHECK'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
    if cursor.fetchone() is None:
        raise SystemExit(
            "PostGIS is not installed in this database. Run:\n"
            "  psql -d <database> -c 'CREATE EXTENSION postgis;'"
        )
PYCHECK
then
    fail "PostGIS check failed — see the message above"
fi

# ── 5. Migrations ────────────────────────────────────────────────────────────
log "5/9 Applying database migrations"
"$PYTHON" manage.py migrate --noinput

# ── 6. Static files ──────────────────────────────────────────────────────────
log "6/9 Collecting static files"
"$PYTHON" manage.py collectstatic --noinput --clear

# ── 7. Translations ──────────────────────────────────────────────────────────
log "7/9 Compiling translations"
if ! "$PYTHON" manage.py compilemessages; then
    warn "    compilemessages failed (gettext missing or no .po files) — continuing"
fi

# ── 8. Restart services + clear sessions ─────────────────────────────────────
log "8/9 Clearing expired sessions and restarting services: $SERVICES"
"$PYTHON" manage.py clearsessions || warn "    clearsessions failed — continuing"
for svc in $SERVICES; do
    log "    restart $svc"
    sudo systemctl restart "$svc"
    sudo systemctl --no-pager --lines=5 status "$svc" || true
done

# ── 9. Healthcheck ───────────────────────────────────────────────────────────
log "9/9 Healthcheck $HEALTHCHECK_URL"
HTTP_CODE="$(curl -k -s -o /dev/null -w '%{http_code}' \
                  --max-time "$HEALTHCHECK_TIMEOUT" \
                  "$HEALTHCHECK_URL" || echo '000')"
case "$HTTP_CODE" in
    2??|3??) log "    healthcheck OK (HTTP $HTTP_CODE)" ;;
    000)     fail "healthcheck failed — could not reach $HEALTHCHECK_URL" ;;
    *)       fail "healthcheck returned HTTP $HTTP_CODE" ;;
esac

log "Deploy of $DEPLOY_REF complete ✓"
