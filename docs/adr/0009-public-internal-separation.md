# 0009 — Public and internal data are separated by construction

**Status:** Accepted

## Context

The register holds two kinds of data in the same records. Some of it is meant to
be public — that an object exists, roughly what condition it is in, where it is.
Some of it must never leave the administration: owner details, contact attempts,
inheritance disputes, research notes, expert reports, internal photographs. A
single leak of the second kind through a public map or an open API would end the
project's acceptance.

Relying on developers to remember which field is which does not scale.

## Decision

Make the separation structural rather than conventional:

- Records carry an explicitly **public description** and an **internal
  description**, not one free-text field with a flag.
- Attached documents carry a visibility that is enforced in querysets, views and
  serializers, not only in templates.
- The API is split into **areas** — public, citizen, administrative, integration
  — with their own serializers. A public serializer never gains a field by
  inheriting from an administrative one.
- Whether an object appears publicly at all is a deliberate release decision on
  the record, not a side effect of its workflow status.
- Tests assert the negative: that public endpoints do not contain internal or
  personal values.

## Consequences

- Some duplication between serializers is accepted; it is the mechanism that
  makes an accidental leak a test failure rather than a deployment.
- Adding a field means deciding its audience, which is the point.
- Municipalities keep the final say: what is released, and which external client
  may read which area, is configuration, not code.
