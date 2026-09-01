from organizations.models import Organization

SESSION_KEY = "active_organization_id"


class OrganizationMiddleware:
    """Attach the current organization to the request.

    Resolution order: the org stored in the session (if the user is still a
    member), otherwise the user's first organization. The result is cached back
    into the session. Anonymous users get ``request.organization = None``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            request.organization = self._resolve(request, user)
        return self.get_response(request)

    def _resolve(self, request, user):
        memberships = Organization.objects.filter(memberships__user=user).distinct()
        active_id = request.session.get(SESSION_KEY)
        if active_id:
            org = memberships.filter(pk=active_id).first()
            if org is not None:
                return org
        org = memberships.first()
        if org is not None:
            request.session[SESSION_KEY] = org.pk
        return org
