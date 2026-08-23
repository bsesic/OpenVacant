#!/usr/bin/env bash
# OpenVacant backup — fast DB + media + .env snapshot.
#
# Writes a timestamped snapshot under $BACKUP_ROOT and (optionally) pushes it
# offsite with restic. Run via the systemd timer (deploy/systemd/openvacant-backup.*).
#
# Install:
#   sudo cp deploy/scripts/backup.sh /usr/local/bin/openvacant-backup.sh
#   sudo chmod +x /usr/local/bin/openvacant-backup.sh
#   sudo mkdir -p /var/backups/openvacant && sudo chmod 700 /var/backups/openvacant
#   sudo cp deploy/systemd/openvacant-backup.{service,timer} /etc/systemd/system/
#   sudo systemctl daemon-reload && sudo systemctl enable --now openvacant-backup.timer
#
# Restore quick-reference:
#   createdb <db> && psql -d <db> -c 'CREATE EXTENSION postgis;'
#   pg_restore -h <host> -U <user> -d <db> -j 4 /var/backups/openvacant/<TS>/db.dump
#   tar -xzf /var/backups/openvacant/<TS>/media.tar.gz -C /opt/openvacant/backend/
#   gpg --decrypt --passphrase-file /etc/openvacant/backup.passphrase env.gpg > backend/.env
#
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/openvacant}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_DIR/backend}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/openvacant}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/etc/openvacant/backup.passphrase}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$TIMESTAMP"

mkdir -p "$DEST"
cd "$DEST"

# Load DATABASE_URL from the app .env.
set -a
# shellcheck disable=SC1091
. "$BACKEND_DIR/.env"
set +a
[ -n "${DATABASE_URL:-}" ] || { echo "DATABASE_URL not set in $BACKEND_DIR/.env"; exit 1; }

# --- 1. PostgreSQL (custom format, compressed) ----
# The scheme may be postgres://, postgresql:// or postgis:// — the application
# accepts all three — so strip whichever one is there before parsing.
DB_URL_BODY="${DATABASE_URL#*://}"
DB_USER=$(echo "$DB_URL_BODY" | sed -E 's|^([^:@/]+).*|\1|')
DB_PASS=$(echo "$DB_URL_BODY" | sed -nE 's|^[^:@/]+:([^@]+)@.*|\1|p')
DB_HOST=$(echo "$DB_URL_BODY" | sed -E 's|.*@([^:/]+).*|\1|')
DB_PORT=$(echo "$DB_URL_BODY" | sed -nE 's|.*:([0-9]+)/.*|\1|p'); DB_PORT="${DB_PORT:-5432}"
DB_NAME=$(echo "$DB_URL_BODY" | sed -E 's|.*/([^/?]+).*|\1|')

PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
    --format=custom --compress=9 --no-owner --no-privileges \
    --exclude-table-data=spatial_ref_sys \
    -f db.dump "$DB_NAME"

# --- 2. Media (user uploads) ----
if [ -d "$BACKEND_DIR/media" ]; then
    tar -czf media.tar.gz -C "$BACKEND_DIR" media/
fi

# --- 3. .env (encrypted at rest if a passphrase is configured) ----
if [ -f "$BACKEND_DIR/.env" ]; then
    if [ -f "$PASSPHRASE_FILE" ]; then
        gpg --batch --yes --symmetric --cipher-algo AES256 \
            --passphrase-file "$PASSPHRASE_FILE" -o env.gpg "$BACKEND_DIR/.env"
    else
        cp "$BACKEND_DIR/.env" env.txt && chmod 600 env.txt
        echo "WARN: $PASSPHRASE_FILE missing — .env saved unencrypted"
    fi
fi

# --- 4. Manifest ----
cat > MANIFEST.txt <<EOF
OpenVacant backup
Timestamp: $TIMESTAMP
Host:      $(hostname -f 2>/dev/null || hostname)
DB:        $DB_NAME @ $DB_HOST:$DB_PORT
DB size:   $(du -h db.dump | cut -f1)
EOF

# --- 5. Offsite push (optional) — restic to B2/S3/etc. when configured ----
if [ -n "${RESTIC_REPOSITORY:-}" ] && command -v restic >/dev/null 2>&1; then
    restic backup "$DEST" --tag openvacant-backup || echo "WARN: restic backup failed"
    restic forget --keep-daily "$RETENTION_DAYS" --prune || true
fi

# --- 6. Local retention ----
find "$BACKUP_ROOT" -maxdepth 1 -type d -name '20*' -mtime +"$RETENTION_DAYS" -exec rm -rf {} +

echo "Backup written to $DEST ($(du -sh "$DEST" | cut -f1))"
