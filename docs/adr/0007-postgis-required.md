# 0007 — PostGIS is a hard requirement

**Status:** Accepted

## Context

Location is not metadata in a vacancy register, it is the primary key of the
domain: reports arrive as map markers, statistics are aggregated per district,
and a property's heritage, redevelopment and funding context is decided by
whether its point falls inside a polygon. The alternatives were storing plain
latitude/longitude columns and doing containment in Python, or requiring PostGIS.

## Decision

Require **PostgreSQL with PostGIS**. `django.contrib.gis` is installed, geometry
fields are used for property points, parcel and district boundaries and imported
geo layers, and the database engine is normalised onto
`django.contrib.gis.db.backends.postgis` even when the connection string says
`postgres://`.

## Consequences

- Spatial containment, distance and clustering queries run in the database, which
  is the only way district statistics and layer context stay fast.
- Every environment needs the spatial stack: the container image installs GEOS,
  GDAL and PROJ, local development and CI use a PostGIS image, and macOS
  developers point `GEOS_LIBRARY_PATH` / `GDAL_LIBRARY_PATH` at Homebrew.
- SQLite is not a supported backend, including for tests.
