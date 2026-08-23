"""Health and readiness probes for load balancers and deployment scripts."""

from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def healthz(request):
    """Liveness probe: the process is up and able to respond."""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Readiness probe: dependencies (database) are reachable."""
    try:
        connections["default"].cursor()
    except OperationalError:
        return JsonResponse({"status": "unavailable", "database": "down"}, status=503)
    return JsonResponse({"status": "ready"})
