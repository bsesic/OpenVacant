from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import ListView
from django_ratelimit.decorators import ratelimit

from apps.geodata.geocoding import GeocodingUnavailable, get_geocoder
from apps.geodata.models import GeoLayer
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
)


class GeoLayerListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    """The layers this municipality has imported, and what they drive."""

    model = GeoLayer
    template_name = "gis/layer_list.html"
    context_object_name = "layers"


@method_decorator(
    ratelimit(key="ip", rate="30/m", method="GET", block=True), name="get"
)
class AddressSearchView(View):
    """Address lookup for the report form.

    Proxied through the server rather than called from the browser: the upstream
    service's terms require a real contact address, and a proxy is also the only
    place the request rate can actually be held down.
    """

    def get(self, request):
        query = (request.GET.get("q") or "").strip()
        if len(query) < 3:
            return JsonResponse({"results": []})
        if (settings.GEOCODER_PROVIDER or "none").lower() == "none":
            return JsonResponse({"results": [], "detail": _("Address search is disabled.")})

        municipality = getattr(request, "municipality", None) or None
        try:
            results = get_geocoder().search(query, municipality=municipality, limit=5)
        except GeocodingUnavailable:
            return JsonResponse(
                {"results": [], "detail": _("The address service is unavailable.")},
                status=503,
            )
        return JsonResponse({"results": results})
