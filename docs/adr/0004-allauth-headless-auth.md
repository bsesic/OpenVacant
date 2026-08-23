# 0004 — Auth with django-allauth (+ headless for API)

**Status:** Accepted

## Context

We need email/password auth, email verification, password reset, social login, and 2FA,
for both server-rendered templates and (later) SPA/mobile clients.

## Decision

Use **django-allauth** as the auth core: session-based template flows, `allauth.mfa`
for TOTP + recovery codes, social providers (Google/Microsoft/Apple/Facebook) enabled
per-provider via env credentials, and mandatory email verification. For SPA/mobile,
mount **`allauth.headless`** at `/_allauth/` (JSON endpoints, session and app-token flows).
DRF endpoints accept session auth (browser) and token auth (programmatic/mobile).

## Consequences

- One mature library covers the whole auth lifecycle; little custom auth code.
- Web uses secure session cookies; mobile uses allauth app tokens — no bespoke JWT layer.
- Provider buttons only appear when configured, so unconfigured installs aren't broken.
