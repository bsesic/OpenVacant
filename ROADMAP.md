# Roadmap

Living plan for **OpenVacant**, a vacancy and potential register for
municipalities. The MVP is a proof of concept for Reichenbach im Vogtland; the
later phases turn it into a federated municipal network.

Each milestone below is tracked as a GitHub issue. Checked items are merged into
`development`.

## MVP — proof of concept

### M0 — Project foundation (#1)
- [ ] Platform foundation imported and rebranded
- [ ] PostGIS enabled end to end (settings, image, CI)
- [ ] Municipal department and contributor roles
- [ ] Citizens no longer become tenant owners on signup
- [ ] `apps/` package for domain apps

### M1 — Municipalities, tenancy and white label (#2)
- [ ] `Municipality` profile on the tenant, with boundary and centre
- [ ] `District` (Ortsteil/Quartier) with geometry
- [ ] Branding without code changes: logo, coat of arms, colours, fonts, domain, legal texts
- [ ] Per-municipality module toggles
- [ ] Resolve the responsible municipality for a coordinate

### M2 — Property record, parcels, vacancy history (#3)
- [ ] `Property` with the full mandatory and optional field set
- [ ] Condition grades and damage markers, separated from expert assessments
- [ ] Status workflow with every transition logged
- [ ] `Parcel` (Flurstück) with geometry
- [ ] Vacancy periods so history is preserved

### M3 — Citizen reporting portal (#4)
- [ ] Report with address or map marker, photos, categories, consent
- [ ] Anonymous reporting with rate limiting and bot protection
- [ ] Moderation queue and conversion into a property record
- [ ] Public map with clustering and filters

### M4 — Verification and task workflow (#5)
- [ ] On-site verification records (confirmed / not confirmed / unclear)
- [ ] Verification by staff, project staff and verified contributors
- [ ] Tasks with type, assignee, due date and completion

### M5 — GIS context, geocoding and heritage (#6)
- [ ] External geo layers per municipality with categories
- [ ] Spatial context lookup for a property
- [ ] Geocoding and reverse geocoding with a pluggable provider
- [ ] GeoJSON layer import, prepared for Saxon geodata and ALKIS
- [ ] Monument records and the heritage check

### M6 — Documents and media (#7)
- [ ] Files per property with a strict public/internal split
- [ ] S3-compatible, tenant-scoped storage

### M7 — Dashboard and statistics (#8)
- [ ] Key figures: recorded, confirmed, open checks, critical, per district and type
- [ ] Time series of new and resolved cases
- [ ] Administration dashboard with KPI tiles, map, recent reports, open tasks

### M8 — API v1 (#9)
- [ ] Public, citizen, administrative and integration areas
- [ ] Scoped, revocable API clients with per-client throttling
- [ ] OpenAPI documentation
- [ ] Tests proving the public/internal separation

### M9 — Participation and reputation (#10)
- [ ] Contributor profile, points, badges, activity level
- [ ] Quality weighted higher than quantity

### M10 — Prepared modules (#11)
- [ ] `owners`, `funding`, `federation` — migration-ready, inactive

### M11 — Privacy and security hardening (#12)
- [ ] Audit log, consent records, retention and purge
- [ ] Role-based field visibility, rate limiting, spam protection
- [ ] API key lifecycle and permission tests

### M12 — Production deployment (#13)
- [ ] NGINX, Gunicorn/Daphne, PostGIS, Redis, email, Celery services
- [ ] Production compose, backups, log rotation
- [ ] Release deployment and rollback

### M13 — Reichenbach seed data and documentation (#14)
- [ ] `seed_demo` for the proof of concept
- [ ] Architecture, getting started, API guide, ADRs

## Success criteria for the proof of concept

The MVP is successful when citizens can report vacancy easily, reports are
reliably located on a map, they can be verified and turned into confirmed
objects, the administration gets a structured record and a traceable workflow,
geodata context can be added, defensible statistics come out, internal and
public data stay separated, data is available through a documented API, the
system installs reproducibly via Docker, and branding can be adapted to a
municipality without code changes.

## After the MVP

### Phase 2 — Owners and activation
Owner portal, claiming and verifying ownership, contact and support processes,
funding programmes, sale and renovation interest.

### Phase 3 — Analysis and urban development
Potential assessment, quarter analyses, brownfields and building gaps, commercial
vacancy, redevelopment management, automated geospatial evaluations.

### Phase 4 — Cooperation and investment
Investor portal, project-related expressions of interest, extended funding
support, structured cooperation between municipality, owners and developers.

### Phase 5 — Federated municipal network
Connecting municipal instances, district and state level, shared citizen
frontends, research and statistics access, standardised open data interfaces.

## Explicitly out of scope for the MVP

Full owner portal, property marketplace, automated valuation, extensive AI damage
analysis, automatic renovation cost calculation, complete funding matching,
nationwide federation, a full research platform, complete land registry
integration, and blanket integration of specialist municipal software.
