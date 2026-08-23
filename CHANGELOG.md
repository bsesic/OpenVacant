# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The MVP scope from the specification, complete and merged. What remains is the
validation itself: running the proof of concept with Reichenbach im Vogtland on
real geodata and real objects.

### Added

**Foundation**
- Project foundation derived from the in-house Django platform foundation, with
  PostGIS enabled end to end and the geospatial libraries in the container image.
- Municipal department roles (building authority, urban planning, property
  management, economic development, regulatory office, heritage authority),
  external public bodies, verified contributors and property owners, with role
  sets for internal access, editing and verification rights.

**Municipalities and white label**
- `Municipality` as a profile on the tenant, with identity, boundary, centre and
  contact details, and a kind so a district or state authority can run an
  instance in a federated setup.
- Districts with their own boundaries — the unit statistics are reported per.
- Branding without code changes: logo, coat of arms, colours, font, domain,
  public introduction, imprint, privacy notice and terms.
- Optional modules switchable per municipality.
- Municipality resolution by tenant, host or single installation, and attribution
  of a coordinate to the municipality whose boundary contains it.

**Property records**
- The property record with the full mandatory and optional field set, controlled
  vocabularies, per-municipality register numbers, condition assessment sources
  and damage markers.
- Verification workflow with an explicit transition table; every change logged
  with actor, reason and note.
- Occupancy kept separate from the workflow status, with a period timeline so
  vacancy duration and history are answerable.
- Parcels as their own model, since a building can sit on several.

**Citizen reporting**
- Reports with categories, description, observed damage, photos, optional
  internal-only contact details and recorded consent.
- Anonymous submission with rate limiting and a honeypot, no account required.
- Moderation queue, and conversion into a record or attachment to an existing
  one.
- Public map with clustering and filters, and a citizen portal with a map picker
  and address search.

**Verification and tasks**
- On-site verification records that drive the record's status, weighted by the
  role held at the time.
- Tasks covering the recurring work, with assignment, due dates and completion.

**Geodata and heritage**
- Geodata layers per municipality with categories that drive the context flags,
  per-hit context records, GeoJSON import with replace semantics, and
  recomputation by command and task.
- Geocoding behind a provider interface, with a server-side proxied address
  search.
- Monument records and heritage checks that outrank layer-derived flags.

**Documents**
- Files per record with visibility enforced in the queryset, a two-release rule
  for anything public, and kinds that can never be published.

**Statistics**
- Single-source reporting definitions, headline figures, breakdowns by district,
  property type and condition, a monthly new-and-resolved series, daily
  snapshots, and the administration dashboard with a filterable map and CSV
  export.

**API**
- Versioned `/api/v1/` with four separated areas: public, citizen,
  administrative and integration.
- API clients with hashed single-view keys, explicit scopes, expiry, rotation,
  revocation and per-client rate limits.
- OpenAPI documentation covering the key scheme and all four areas.

**Participation**
- Contributor profiles, explainable point entries, threshold levels and badges,
  weighted so that being right counts for more than being prolific.

**Prepared for later phases**
- Owners with contact states and administration-verified ownership claims,
  funding programmes with per-object progress, and federation with explicit
  per-category sharing that defaults to nothing.

**Privacy and security**
- Access log for personal and internal data, readable by managers.
- Consent records stored independently of the report.
- Retention rules for discarded reports, submitting addresses, contact details
  and the log itself, applied by command and nightly task.
- Uploaded files are not reachable by URL: downloads go through views that
  authorise the caller and then hand the file to the web server.

**Deployment**
- NGINX with TLS, security headers, rate limits and protected file delivery;
  Gunicorn and Daphne units; Celery worker, scheduler and Flower; PostGIS and
  Redis; email relay; production compose; backups; release deployment and
  rollback.

**Documentation**
- Architecture overview, API guide, getting started, deployment reference and
  runbook, nine architecture decision records, and a seed command that builds a
  browsable demonstration instance for Reichenbach im Vogtland.

### Changed
- Signing up no longer creates a tenant. Tenants are municipalities onboarded by
  the instance operator, so a citizen holds no membership.
- German is the default language and `Europe/Berlin` the default time zone.
- Celery runs eagerly throughout the test suite, so tests need no broker.

### Removed
- The generic document example app from the platform foundation, replaced by
  property-attached media with a public/internal split.
- The state machine library, replaced by the explicit logged transition table,
  and the Elasticsearch backend, replaced by Postgres full-text search.

### Fixed
- A Celery integration test hung indefinitely: assigning
  `app.conf.task_always_eager` is overridden on every read by the lazy Django
  settings source.
- API requests authenticated by token or API key had no tenant, because the
  tenancy middleware runs before DRF authenticates.
- The backup script only parsed `postgres://` URLs and would have produced a
  broken dump on a `postgis://` deployment.
- Demonstration accounts were unusable without a mail server, because email
  verification is mandatory.

[Unreleased]: https://github.com/bsesic/OpenVacant/commits/development
