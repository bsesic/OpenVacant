from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    label = "integrations"
    verbose_name = _("Integrations")

    def ready(self):
        # Registers the OpenAPI security scheme for the API key authenticator.
        from apps.integrations import schema  # noqa: F401
