# 0006 — Vite asset pipeline (replacing vue-cli)

**Status:** Accepted

## Context

The initial frontend used `@vue/cli-service` (vue-cli), which is end-of-life and pulled
in many vulnerable transitive dependencies. Templates-first still needs a CSS/JS build
(Bootstrap 5 from SCSS) wired into Django templates.

## Decision

Replace vue-cli with **Vite** via **django-vite**. Vite builds Bootstrap SCSS + JS into
`backend/static/dist/` with a manifest; `django-vite` emits the right tags per environment
(HMR dev server when `DEBUG`, manifest-based hashed assets in production). Vue remains
available for progressive enhancement.

## Consequences

- Removes the EOL vue-cli dependency tree and its CVEs; modern, fast builds.
- Production deploys must run `npm ci && npm run build` before `collectstatic`
  (wired into `deploy.sh`).
- Vite 7+/recent toolchain wants **Node 20+**; build on a Node 20 host.
- When merging frontend PRs, watch `package-lock.json` for bad merge resolutions
  (see troubleshooting).
