# Architecture Decision Records

Short records of the significant, hard-to-reverse decisions behind OpenVacant.
Each ADR has a status (Proposed / Accepted / Superseded), the context, the decision,
and its consequences. New decisions get the next number; superseded ones stay for history.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-templates-first.md) | Templates-first UI; REST API later | Accepted |
| [0002](0002-monolithic-settings.md) | Single settings module via django-environ | Accepted |
| [0003](0003-organization-fk-multitenancy.md) | Multi-tenancy via Organization FK row-scoping | Accepted |
| [0004](0004-allauth-headless-auth.md) | Auth with django-allauth (+ headless for API) | Accepted |
| [0005](0005-stripe-only-billing.md) | Stripe-only billing | Accepted |
| [0006](0006-vite-asset-pipeline.md) | Vite asset pipeline (replacing vue-cli) | Accepted |
| [0007](0007-postgis-required.md) | PostGIS is a hard requirement | Accepted |
| [0008](0008-municipality-profile-on-tenant.md) | Municipality as a profile on the tenant | Accepted |
| [0009](0009-public-internal-separation.md) | Public and internal data separated by construction | Accepted |

Background and the module map: [`../architecture.md`](../architecture.md).
