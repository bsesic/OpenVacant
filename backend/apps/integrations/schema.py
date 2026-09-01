"""OpenAPI description of the API key scheme.

Without this, the generated documentation shows the endpoints but not how to
authenticate against them, which for an API-first product is half a document.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.integrations.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "Scoped key issued by a municipality, sent as "
                "`Authorization: ApiKey <key>`. Keys carry an explicit list of "
                "scopes, may expire, and can be rotated or revoked by the "
                "municipality at any time."
            ),
        }
