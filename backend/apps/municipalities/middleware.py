from django.utils.functional import SimpleLazyObject

from apps.municipalities.resolution import resolve_municipality


class MunicipalityMiddleware:
    """Attach the municipality this request is about to ``request.municipality``.

    Resolved lazily: most requests (static files, health probes, the API schema)
    never look at it, and resolution costs a query.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.municipality = SimpleLazyObject(lambda: resolve_municipality(request))
        return self.get_response(request)
