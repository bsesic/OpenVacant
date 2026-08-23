# 0001 — Templates-first UI, REST API later

**Status:** Accepted for the UI; the API is not deferred (see [0009](0009-public-internal-separation.md))

## Context

The starting code mixed a decoupled Vue SPA (JWT) with a roadmap that also described
server-rendered Django templates. We had to pick the primary UI surface. The product
will also have mobile apps (android/react-native/swift dirs exist), which need a JSON API.

## Decision

Server-rendered **Django templates are the primary UI**. The DRF REST API is built
**later** (Phase 8) as a versioned, tenant-scoped layer that feeds the Vue web client
and future mobile apps. Auth is session-based for templates and adds JSON/token flows
(allauth headless) for the API.

## Consequences

- Faster initial delivery; SEO-friendly pages out of the box; no SPA build required to ship.
- Vue is used for progressive enhancement, not as the whole UI (full SPA deferred).
- The API arrives once the template app is solid, avoiding building two UIs at once.
