# Roadmap

Living plan for **OpenVacant**, a vacancy and potential register for
municipalities. The MVP is a proof of concept for Reichenbach im Vogtland; the
later phases turn it into a federated municipal network.

Each milestone below is tracked as a GitHub issue. Checked items are merged into
`development`.

## MVP — proof of concept

All milestones below are merged into `development`. What remains is the
validation the specification asks for: running the proof of concept with
Reichenbach im Vogtland, on real geodata and real objects.

### M0 — Project foundation (#1)
- [x] Platform foundation imported and rebranded
- [x] PostGIS enabled end to end (settings, image, CI)
- [x] Municipal department and contributor roles
- [x] Citizens no longer become tenant owners on signup
- [x] `apps/` package for domain apps

### M1 — Municipalities, tenancy and white label (#2)
- [x] `Municipality` profile on the tenant, with boundary and centre
- [x] `District` (Ortsteil/Quartier) with geometry
- [x] Branding without code changes: logo, coat of arms, colours, fonts, domain, legal texts
- [x] Per-municipality module toggles
- [x] Resolve the responsible municipality for a coordinate

### M2 — Property record, parcels, vacancy history (#3)
- [x] `Property` with the full mandatory and optional field set
- [x] Condition grades and damage markers, separated from expert assessments
- [x] Status workflow with every transition logged
- [x] `Parcel` (Flurstück) with geometry
- [x] Vacancy periods so history is preserved

### M3 — Citizen reporting portal (#4)
- [x] Report with address or map marker, photos, categories, consent
- [x] Anonymous reporting with rate limiting and bot protection
- [x] Moderation queue and conversion into a property record
- [x] Public map with clustering and filters

### M4 — Verification and task workflow (#5)
- [x] On-site verification records (confirmed / not confirmed / unclear)
- [x] Verification by staff, project staff and verified contributors
- [x] Tasks with type, assignee, due date and completion

### M5 — GIS context, geocoding and heritage (#6)
- [x] External geo layers per municipality with categories
- [x] Spatial context lookup for a property
- [x] Geocoding and reverse geocoding with a pluggable provider
- [x] GeoJSON layer import, prepared for Saxon geodata and ALKIS
- [x] Monument records and the heritage check

### M6 — Documents and media (#7)
- [x] Files per property with a strict public/internal split
- [x] S3-compatible, tenant-scoped storage

### M7 — Dashboard and statistics (#8)
- [x] Key figures: recorded, confirmed, open checks, critical, per district and type
- [x] Time series of new and resolved cases
- [x] Administration dashboard with KPI tiles, map, recent reports, open tasks

### M8 — API v1 (#9)
- [x] Public, citizen, administrative and integration areas
- [x] Scoped, revocable API clients with per-client throttling
- [x] OpenAPI documentation
- [x] Tests proving the public/internal separation

### M9 — Participation and reputation (#10)
- [x] Contributor profile, points, badges, activity level
- [x] Quality weighted higher than quantity

### M10 — Prepared modules (#11)
- [x] `owners`, `funding`, `federation` — migration-ready, inactive

### M11 — Privacy and security hardening (#12)
- [x] Audit log, consent records, retention and purge
- [x] Role-based field visibility, rate limiting, spam protection
- [x] API key lifecycle and permission tests

### M12 — Production deployment (#13)
- [x] NGINX, Gunicorn/Daphne, PostGIS, Redis, email, Celery services
- [x] Production compose, backups, log rotation
- [x] Release deployment and rollback

### M13 — Reichenbach seed data and documentation (#14)
- [x] `seed_demo` for the proof of concept
- [x] Architecture, getting started, API guide, ADRs

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
