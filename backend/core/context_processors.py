from django.conf import settings


def analytics(request):
    """Expose privacy-analytics config to templates (rendered in the base layout)."""
    return {
        "ANALYTICS_PROVIDER": settings.ANALYTICS_PROVIDER,
        "PLAUSIBLE_DOMAIN": settings.PLAUSIBLE_DOMAIN,
        "PLAUSIBLE_SRC": settings.PLAUSIBLE_SRC,
        "MATOMO_URL": settings.MATOMO_URL,
        "MATOMO_SITE_ID": settings.MATOMO_SITE_ID,
    }
