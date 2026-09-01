# 0008 — Municipality as a profile on the tenant

**Status:** Accepted
**Amends:** [0003](0003-organization-fk-multitenancy.md)

## Context

The foundation models a tenant as `Organization` and auto-creates a personal
organization for every account. Neither fits this domain. A tenant here is a
public body, and the people who sign up in the largest numbers are citizens
filing reports — they must not become the owner of anything. At the same time the
specification anticipates federation, where a district or a state office runs an
instance above the municipalities, so "tenant" is not always "municipality".

The options were to rename and replace the tenancy machinery with a
`Municipality` model, or to keep `Organization` as the tenancy primitive and
attach the municipal profile to it.

## Decision

Keep `Organization` as the **tenancy primitive** — membership, roles, invitations
and `request.organization` are unchanged — and model the municipality as a
**profile attached to it** in the `municipalities` app, carrying the official
name, boundary, centre, branding and enabled modules.

Signing up no longer creates a tenant. A user with no membership is a citizen.
Creating a tenant is reserved for the instance operator, and `Role` is extended
with municipal department roles, external public bodies and verified
contributors.

## Consequences

- Improvements to the shared foundation stay mergeable, because the tenancy code
  is untouched.
- A non-municipal tenant (district, state office) reuses the same membership
  machinery without a special case, which is what federation needs.
- The price is two models for one real-world concept. The rule is: tenancy code
  says `Organization`, everything user-facing and professional says
  `Municipality`.
- Views that require a tenant deny citizens instead of offering to create one.
