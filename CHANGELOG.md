# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project foundation for the vacancy register, derived from the in-house Django
  platform foundation: templates-first Django 5.1 monorepo with backend,
  frontend asset pipeline, deployment configuration and documentation.
- PostGIS support end to end: `django.contrib.gis`, the spatial database
  backend, geospatial libraries in the container image and a PostGIS service in
  local development and CI.
- Municipal department roles (building authority, urban planning, property
  management, economic development, regulatory office, heritage authority),
  external public bodies, verified contributors and property owners, with role
  sets for internal access, editing and verification rights.
- `compliance.exporters` registry so domain apps can contribute to the personal
  data export without the compliance app importing them.
- Reusable role mixins for views: internal area, editing staff and verification.

### Changed
- Signing up no longer creates a personal tenant. Tenants are municipalities
  onboarded by the instance operator, so citizens hold no membership and tenant
  creation is limited to operator accounts.
- German is the default language and `Europe/Berlin` the default time zone.
- Celery runs eagerly throughout the test suite, so tests never require a broker
  or a worker.

### Removed
- The generic document example app from the platform foundation. Documents are
  reintroduced as property-attached media with a public/internal split.

### Fixed
- The Celery integration test hung indefinitely because it set
  `app.conf.task_always_eager`, which is overridden on every read by the lazy
  Django settings source. The Django setting is now overridden instead.

[Unreleased]: https://github.com/bsesic/OpenVacant/commits/development
