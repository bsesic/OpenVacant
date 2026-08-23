"""Working out which municipality an API request concerns."""

from apps.municipalities.models import Municipality


def api_organization(request):
    """The tenant this API request is about.

    Resolution has to happen here rather than relying on
    ``OrganizationMiddleware``: the middleware runs before DRF authenticates, so
    a token or API-key caller has no ``request.organization`` at all. Only a
    session-authenticated person does.

    Order, most to least specific:

    1. an external client belongs to exactly one municipality — that is the
       point of issuing it a key;
    2. the tenant resolved for a session, which honours the user's tenant switch;
    3. the authenticated user's membership. Someone who works for several
       municipalities and calls with a token gets their first one, since a
       stateless request carries no choice;
    4. the municipality of a white-label installation, for anonymous public
       calls. Nothing when the instance holds several — a public endpoint must
       never quietly answer for the wrong town.
    """
    client = getattr(request, "api_client", None)
    if client is not None:
        return client.organization

    organization = getattr(request, "organization", None)
    if organization is not None:
        return organization

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and getattr(user, "pk", None):
        membership_organization = user.organizations.first()
        if membership_organization is not None:
            return membership_organization

    municipality = getattr(request, "municipality", None) or None
    if municipality:
        return municipality.organization

    if Municipality.objects.count() == 1:
        return Municipality.objects.first().organization
    return None
