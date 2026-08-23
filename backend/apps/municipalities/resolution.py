"""Deciding which municipality a request or a coordinate belongs to."""

from django.conf import settings

from apps.municipalities.models import Municipality


def municipality_for_point(point):
    """The municipality whose boundary contains ``point``, or None.

    This is the routing rule a shared citizen frontend would use: a report is
    handed to the instance responsible for the place it describes. Municipalities
    without an imported boundary never match, so an unattributable report is
    surfaced rather than silently assigned to the wrong body.
    """
    if point is None:
        return None
    return Municipality.objects.filter(boundary__contains=point).first()


def municipality_for_host(host):
    """The municipality configured for ``host``, or None.

    The port is stripped so a development host like ``example.test:8000``
    still matches the configured domain.
    """
    if not host:
        return None
    hostname = host.split(":")[0].lower()
    return Municipality.objects.filter(domain__iexact=hostname).first()


def resolve_municipality(request):
    """The municipality this request is about.

    Resolution order, from most to least specific:

    1. the tenant the signed-in user is working in — an authority employee sees
       their own municipality regardless of the host;
    2. the host, so one deployment can serve several branded domains;
    3. the only municipality on the instance, which is the normal white-label
       case where a municipality runs its own installation.

    Returns None when the instance holds several municipalities and the request
    identifies none of them.
    """
    organization = getattr(request, "organization", None)
    if organization is not None:
        municipality = Municipality.objects.filter(organization=organization).first()
        if municipality is not None:
            return municipality

    municipality = municipality_for_host(request.get_host())
    if municipality is not None:
        return municipality

    if Municipality.objects.count() == 1:
        return Municipality.objects.first()
    return None


def map_defaults(municipality=None):
    """Map centre and zoom for a municipality, falling back to the instance."""
    latitude = settings.MAP_DEFAULT_LATITUDE
    longitude = settings.MAP_DEFAULT_LONGITUDE
    zoom = settings.MAP_DEFAULT_ZOOM
    if municipality is not None:
        if municipality.centre is not None:
            latitude = municipality.centre.y
            longitude = municipality.centre.x
        if municipality.default_zoom:
            zoom = municipality.default_zoom
    return {
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
        "tile_url": settings.MAP_TILE_URL,
        "tile_attribution": settings.MAP_TILE_ATTRIBUTION,
    }
