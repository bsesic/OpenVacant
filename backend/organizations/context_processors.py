def organizations(request):
    """Expose the current organization and the user's organizations to templates."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "current_organization": getattr(request, "organization", None),
        "user_organizations": user.organizations.all(),
    }
