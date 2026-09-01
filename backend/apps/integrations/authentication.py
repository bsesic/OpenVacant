"""API key authentication for external clients."""

from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle

from apps.integrations.models import ApiClient, hash_key

HEADER_SCHEME = "ApiKey"


class ApiKeyUser:
    """Stands in for a user so DRF's machinery has something to work with.

    An external client is not a person: it has no profile, no memberships and no
    session. Modelling it as a fake user account would put a row in the user
    table that could be signed into.
    """

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, client):
        self.client = client
        self.pk = None

    def __str__(self):
        return f"api-client:{self.client.name}"

    def has_perm(self, *args, **kwargs):
        return False

    def has_module_perms(self, *args, **kwargs):
        return False


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate ``Authorization: ApiKey <key>``.

    The key is looked up by its prefix and verified against the stored hash, so
    the secret itself never has to exist in the database.
    """

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != HEADER_SCHEME:
            return None

        raw_key = parts[1]
        client = (
            ApiClient.objects.filter(key_prefix=raw_key[:8])
            .filter(key_hash=hash_key(raw_key))
            .select_related("organization")
            .first()
        )
        if client is None:
            raise exceptions.AuthenticationFailed(_("Unknown API key."))
        if not client.is_active:
            raise exceptions.AuthenticationFailed(_("This API key has been revoked."))
        if client.is_expired:
            raise exceptions.AuthenticationFailed(_("This API key has expired."))

        client.record_use()
        request.api_client = client
        return ApiKeyUser(client), client

    def authenticate_header(self, request):
        return HEADER_SCHEME


def request_client(request):
    """The API client behind this request, or None when a person is calling."""
    return getattr(request, "api_client", None)


class HasApiScope(BasePermission):
    """Require the declared scope when the caller is an external client.

    Views set ``required_scope``. Human callers are unaffected: their rights come
    from their role in the municipality, not from a scope.
    """

    message = _("This API key does not carry the required scope.")

    def has_permission(self, request, view):
        client = getattr(request, "api_client", None)
        if client is None:
            return True
        required = getattr(view, "required_scope", None)
        if required is None:
            return False
        return client.has_scope(required)


class HumanUserRateThrottle(UserRateThrottle):
    """The per-user limit, but only for actual people.

    An API key caller has no user primary key, so the standard user throttle
    would put every external client into one shared bucket. Their limit is
    ``ApiClientThrottle``, taken from the client's own configuration.
    """

    def get_cache_key(self, request, view):
        if getattr(request, "api_client", None) is not None:
            return None
        return super().get_cache_key(request, view)


class ApiClientThrottle(SimpleRateThrottle):
    """Per-client rate limit, taken from the client's own configuration.

    A shared limit would let one busy integration starve the others, and the
    municipality wants to be able to slow down a single client.
    """

    scope = "api_client"

    def get_cache_key(self, request, view):
        client = getattr(request, "api_client", None)
        if client is None:
            return None
        return f"throttle_api_client_{client.pk}"

    def get_rate(self):
        # The real rate is resolved per client in allow_request.
        return "1000/hour"

    def allow_request(self, request, view):
        client = getattr(request, "api_client", None)
        if client is None:
            return True
        self.rate = client.throttle_rate or "1000/hour"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
