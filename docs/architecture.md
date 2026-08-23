# Architecture

OpenVacant is a modular Django monolith. The specification calls for an
API-first, headless, modular and federatable system; none of that requires
microservices at this stage, and a single deployable unit is what a municipality
can realistically operate. The module boundaries are drawn so that individual
services can be extracted later without redesigning the domain.

## Layers

```
                     ┌──────────────────────┐   ┌──────────────────────┐
                     │  Citizen portal      │   │  Administration UI   │
                     │  (report, map)       │   │  (records, tasks)    │
                     └───────────┬──────────┘   └──────────┬───────────┘
                                 │                         │
                     ┌───────────▼─────────────────────────▼───────────┐
                     │                  /api/v1/                       │
                     │  public │ citizen │ administrative │ integration │
                     └───────────────────────┬─────────────────────────┘
                                             │
                     ┌───────────────────────▼─────────────────────────┐
                     │              Domain apps (backend/apps)         │
                     └───────────────────────┬─────────────────────────┘
                                             │
                     ┌───────────────────────▼─────────────────────────┐
                     │  PostGIS  ·  Redis + Celery  ·  Object storage  │
                     └─────────────────────────────────────────────────┘
```

The citizen portal talks to the core only through the versioned API, so it can be
replaced by a separate application — or, later, by a shared nationwide frontend
that routes a report to the responsible instance by its coordinates.

## Modules

### Platform apps (`backend/`)

| App | Responsibility |
|-----|----------------|
| `users` | Custom user model, profile, GDPR soft-delete state |
| `organizations` | Tenancy: membership, roles, invitations, `request.organization` |
| `pages` | Public static pages, contact form, legal texts |
| `notifications` | In-app notifications |
| `compliance` | Personal data export, account deletion, retention |
| `billing` | Optional subscription handling; degrades gracefully when unset |
| `newsletter` | Opt-in mailing list with double opt-in |
| `api` | Versioned API wiring |

### Domain apps (`backend/apps/`)

| App | Responsibility |
|-----|----------------|
| `municipalities` | Municipality profile on the tenant, districts, branding, module toggles |
| `properties` | The property record: the professional core |
| `parcels` | Cadastral parcels |
| `vacancies` | Vacancy periods, so vacancy history is preserved |
| `reports` | Citizen reports, moderation, conversion into records |
| `inspections` | On-site verification results |
| `workflows` | Tasks and assignments |
| `gis` | External geo layers, spatial context, geocoding |
| `heritage` | Monument records and heritage checks |
| `documents` | Files per property, public or internal |
| `statistics` | Key figures and snapshots |
| `integrations` | External API clients: keys, scopes, revocation |
| `participation` | Contributor reputation, prepared for gamification |
| `owners`, `funding`, `federation` | Prepared for later phases, inactive by default |

## Cross-cutting rules

**Tenant scoping.** Everything professional is scoped to a tenant. Models inherit
`OrganizationOwnedModel`; views combine `CurrentOrganizationRequiredMixin` with
`OrgScopedQuerysetMixin`. Isolation is enforced in querysets, so a new model that
skips the base class is a bug.

**Roles.** `organizations.Role` covers tenant administration, the municipal
departments, external public bodies and verified contributors. Views declare
intent through role mixins (`InternalAreaRequiredMixin`, `StaffRoleRequiredMixin`,
`VerificationRoleRequiredMixin`) rather than checking roles inline.

**Public versus internal.** See [ADR 0009](adr/0009-public-internal-separation.md).
The split runs through the models, the querysets and the serializers — not through
template logic.

**Geodata.** See [ADR 0007](adr/0007-postgis-required.md). Containment and
aggregation happen in the database.

**Auditability.** Status changes on a record are logged as transitions with actor,
timestamp and reason. A report never becomes a confirmed vacancy implicitly.

**Background work.** Anything slow — geocoding, layer imports, statistics
snapshots, notification fan-out — is a Celery task.

## Federation

A municipality decides which data leaves its instance. The `federation` app models
peer instances and a share scope per data category. Because the responsible
municipality for a coordinate can be resolved from the district and municipality
boundaries, a report can be routed to the right instance without a central
registry.
