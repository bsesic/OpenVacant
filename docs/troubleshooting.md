# Troubleshooting

Common failures and fixes. Most were hit while building the boilerplate.

## Setup & database

**`role "openvacant" does not exist` / cannot connect to Postgres**
Start infra (`docker compose up -d db redis`) or point `DATABASE_URL` at a real Postgres.
The default expects DB/user/password all `openvacant`.

**`InconsistentMigrationHistory` or custom-user errors after first migrate**
`AUTH_USER_MODEL = "users.User"` must be set before the very first migration. If you
changed it late, drop the dev database and re-migrate from scratch.

**Tests need a database but Docker isn't running**
For a quick local run, point pytest at SQLite: `DATABASE_URL="sqlite:///t.sqlite3" pytest`.
CI runs the real Postgres + Redis matrix.

## Frontend / Vite

**Page has no styles / 404s for `/static/dist/...` in development**
Run the Vite dev server (`cd frontend && npm run dev`); with `DEBUG=True` django-vite
points at it. Without it, either start it or build (`npm run build`) and set `DEBUG=False`.

**Production page missing CSS/JS**
Assets weren't built before `collectstatic`. Run `npm ci && npm run build` (this is in
`deploy.sh`). Confirm `backend/static/dist/.vite/manifest.json` exists.

**`npm run build` fails / EBADENGINE warnings**
The toolchain (Vite 7+/sass) wants **Node 20+**. Build on Node 20.

**`package-lock.json` ballooned to thousands of lines after a merge**
A bad merge re-introduced old (vue-cli) lock entries. Fix:
`rm frontend/package-lock.json && (cd frontend && npm install)`, then commit. A healthy
lock for the Vite setup is a few hundred lines with no `@vue/cli`/`axios`/`core-js`.

## Auth

**allauth settings deprecation warnings**
This project uses the modern names (`ACCOUNT_LOGIN_METHODS`, `ACCOUNT_SIGNUP_FIELDS`);
don't reintroduce the old `ACCOUNT_AUTHENTICATION_METHOD`/`ACCOUNT_*_REQUIRED`.

**Social login button missing**
A provider only renders when both `<PROVIDER>_CLIENT_ID` and `<PROVIDER>_SECRET` are set.
Apple additionally needs `APPLE_KEY_ID` and `APPLE_CERTIFICATE_KEY` (the `.p8`).

## Billing

**Billing UI says "not configured" / checkout disabled**
Set `STRIPE_SECRET_KEY` (and price ids). Billing self-disables without it.

**Webhook returns 400**
Signature verification failed — check `STRIPE_WEBHOOK_SECRET` matches the endpoint's
signing secret. Events are idempotent (deduped by event id), so safe to retry.

## Background jobs

**Tasks never run**
Start a worker (`celery -A core worker -l info`) and ensure `CELERY_BROKER_URL`/Redis is
reachable. In tests, set `CELERY_TASK_ALWAYS_EAGER=True` to run inline.

## Environment

**Background commands get "killed", `ENOSPC: no space left on device`**
The disk is full. Check `df -h /`; free space (`pip cache purge`, `npm cache clean --force`,
remove stale build artifacts). A full APFS container silently kills long-running processes.

**Rate-limit counters leak between tests (unexpected 403 on the contact form)**
The test suite clears the cache between tests (autouse fixture in `conftest.py`). If you
add cache-based tests, rely on that or clear the cache explicitly.
