# 0002 — Single settings module via django-environ

**Status:** Accepted

## Context

Django projects often split settings into `base/dev/prod`. The reference projects
(spielekiste, immobot, AlchemyPy) instead use one settings module driven by environment
variables, which the maintainer is fluent with.

## Decision

Keep **one `core/settings.py`** read through **django-environ**, with a single
`DEBUG` flag and an `if not DEBUG:` production hardening block (HSTS, secure cookies,
SSL redirect, etc.). All configuration comes from the environment; `.env.example`
documents every variable. Optional integrations (S3, Stripe, social, analytics)
self-disable when their variables are unset.

## Consequences

- One place to read; no settings-module import gymnastics; matches existing repos.
- Environment parity between dev and prod (same module, different env).
- Secrets never live in code; deployment supplies `.env`.
