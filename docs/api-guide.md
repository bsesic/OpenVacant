# API guide

The API is a core component of OpenVacant, not an addition. It has four
separated areas, and the separation is structural: each area has its own
serializers, so a field cannot reach the public surface by inheriting from an
administrative one. See [ADR 0009](adr/0009-public-internal-separation.md).

Interactive documentation: `/api/docs/` (Swagger) and `/api/redoc/`. Machine
readable schema: `/api/schema/`.

| Area | Base path | Who |
|------|-----------|-----|
| Public | `/api/v1/public/` | Anyone. Released objects and aggregated figures. |
| Citizen | `/api/v1/citizen/` | Anyone may submit; an account is needed to list your own. |
| Administration | `/api/v1/admin/` | Municipal staff, or a client granted internal access. |
| Integration | `/api/v1/integration/` | External clients: geodata metadata and self-introspection. |

## Authentication

Three ways in, depending on who is calling.

**Nothing** — the public area needs no credentials at all, and submitting a
report does not either, mirroring the anonymous web form.

**A session** — municipal staff signed into the web interface can call the API
from the same browser.

**An API key** — external systems. The municipality issues one under
*API clients*, and it is shown exactly once:

```http
GET /api/v1/public/properties/ HTTP/1.1
Authorization: ApiKey ov_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Keys are stored only as a hash, so a database dump does not yield working
credentials — and a lost key is replaced, not recovered.

## Scopes

A key carries an explicit list of what it may do. Granting one does not imply
another; in particular, reading published objects says nothing about reading the
case files.

| Scope | Grants |
|-------|--------|
| `read_public` | Released objects. |
| `read_statistics` | Key figures. |
| `read_internal` | The professional data in the administrative area. |
| `read_geodata` | Geodata layer metadata. |
| `write_reports` | Submitting reports. |

A client can ask what it holds rather than discovering it from a sequence of
refusals:

```bash
curl -H "Authorization: ApiKey $KEY" https://example.org/api/v1/integration/client/
```

Keys can expire, be rotated and be revoked, all from the administration UI. A
revoked or rotated-away key stops working on the next request.

## Rate limits

Each client carries its own limit, so one busy integration cannot starve the
others. Anonymous callers and signed-in people have their own limits, and report
submission is limited separately. Exceeding a limit gives `429`.

## Public area

```bash
# Released objects
curl https://example.org/api/v1/public/properties/

# Only confirmed vacancy, one district
curl "https://example.org/api/v1/public/properties/?vacant=1&district=Innenstadt"

# One object, addressed by its register reference rather than a database id
curl https://example.org/api/v1/public/properties/145-2026-0001/

# Key figures
curl https://example.org/api/v1/public/statistics/
```

What the public area deliberately does **not** contain: internal descriptions,
sources, owner information, contact details, unreleased documents, database
identifiers, and the operational figures (open tasks, reports in moderation)
that describe the administration's workload rather than vacancy.

An installation serving several municipalities answers nothing here unless the
request identifies one, by host or by key. Answering for the wrong town is worse
than not answering.

The public area can be switched off per municipality.

## Citizen area

Submitting a report. Either a coordinate or an address is enough, and consent is
mandatory and recorded:

```bash
curl -X POST https://example.org/api/v1/citizen/reports/ \
  -H "Content-Type: application/json" \
  -d '{
    "category": "suspected_vacancy",
    "description": "Boarded up for over a year.",
    "latitude": 50.6236,
    "longitude": 12.3036,
    "damage": ["roof", "windows"],
    "accepted_privacy_policy": true,
    "accepted_terms": true
  }'
```

Listing your own reports needs an account. Nothing here reads anybody else's
data, and anonymous reports cannot be tied back to an account — that is what
submitting anonymously means.

## Administrative area

Needs an internal role, or a key with `read_internal`. Being signed in is not
enough: a citizen with an account is refused.

```bash
curl -H "Authorization: ApiKey $KEY" https://example.org/api/v1/admin/properties/
curl -H "Authorization: ApiKey $KEY" https://example.org/api/v1/admin/statistics/
```

Available: `properties` (read and write), `reports`, `inspections` (read),
`tasks` (read and write), `statistics`.

The workflow status is **read only** here, as it is in the web interface. A
record's status changes through its own action so that every change is logged
with who made it and why; allowing a `PATCH` to set it would put a hole in the
audit trail. The response carries `allowed_transitions` so a client knows what
is possible.

## Integration area

```bash
curl -H "Authorization: ApiKey $KEY" https://example.org/api/v1/integration/geodata-layers/
```

Layer metadata: name, category, source, licence, feature count, import date. The
geometry itself is not served here; layers are imported into an instance from the
municipality's own sources.

## Versioning

The version is in the path. `/api/v1/` is stable: fields are added, not removed
or repurposed. A change that would break a client gets `/api/v2/`.

## For an open data portal

Give the portal a key with `read_public` and `read_statistics` only, and set an
expiry so the access has to be renewed deliberately:

```bash
curl -H "Authorization: ApiKey $KEY" \
     "https://example.org/api/v1/public/properties/?vacant=1" \
     -H "Accept: application/json"
```

Data licensing is the municipality's decision. Each geodata layer carries its own
licence field, and imported layers may bring conditions from their source.
