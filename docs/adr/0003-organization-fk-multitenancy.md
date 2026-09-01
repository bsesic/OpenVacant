# 0003 — Multi-tenancy via Organization FK row-scoping

**Status:** Accepted, amended by [0008](0008-municipality-profile-on-tenant.md)

## Context

SaaS needs tenant isolation. Options: schema/DB-per-tenant (e.g. django-tenants) or
shared tables with row-level scoping by a tenant foreign key.

## Decision

Use **shared tables with an `Organization` foreign key** (row-scoping). Tenant-scoped
models inherit `OrganizationOwnedModel`; views use `OrgScopedQuerysetMixin` +
`CurrentOrganizationRequiredMixin`; `OrganizationMiddleware` sets `request.organization`
from the session (with a first-membership fallback). Subscriptions attach to the Org.
Roles are Owner/Admin/Member; ADR 0008 extends the roles and removes the
automatic personal organization.

## Consequences

- Simple operations (one database, standard migrations) — right for early-stage SaaS.
- Isolation is enforced in code (querysets/mixins), so new models must use the base/mixins.
- If extreme isolation/compliance later demands it, migrating to schema-per-tenant is a
  larger change — revisit only under real need.
