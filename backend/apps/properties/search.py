"""Text search over property records.

Postgres full-text search is enough here and needs no extra infrastructure. The
important part is the ``include_internal`` switch: internal wording must never
be searchable from a public surface, because a hit is itself a disclosure.
"""

from django.contrib.postgres.search import SearchQuery, SearchVector

PUBLIC_FIELDS = ("reference", "street", "city", "postal_code", "public_description")
INTERNAL_FIELDS = ("internal_description", "sources", "address_note")


def search_properties(queryset, query, include_internal=False):
    """Filter ``queryset`` by ``query``, returning it unchanged when empty."""
    query = (query or "").strip()
    if not query:
        return queryset
    fields = PUBLIC_FIELDS + (INTERNAL_FIELDS if include_internal else ())
    vector = SearchVector(*fields)
    # plain search keeps the behaviour predictable for the short address-like
    # queries people actually type.
    return queryset.annotate(search=vector).filter(search=SearchQuery(query, search_type="plain"))
