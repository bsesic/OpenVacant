"""Registry for personal-data export contributions.

The GDPR export view must not import domain apps, otherwise compliance would
depend on every feature. Instead, an app registers a collector in its AppConfig's
``ready()``:

    from compliance.exporters import register_export_collector

    def _collect(user):
        return {"reports": [...]}

    register_export_collector(_collect)

Each collector receives the user and returns a JSON-serialisable mapping that is
merged into the export payload.
"""

_COLLECTORS = []


def register_export_collector(collector):
    """Register a callable ``collector(user) -> dict`` for the data export."""
    if collector not in _COLLECTORS:
        _COLLECTORS.append(collector)
    return collector


def collect_personal_data(user):
    """Merge every registered collector's contribution for ``user``."""
    data = {}
    for collector in _COLLECTORS:
        contribution = collector(user) or {}
        data.update(contribution)
    return data
