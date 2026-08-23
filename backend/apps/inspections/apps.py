from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InspectionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inspections"
    label = "inspections"
    verbose_name = _("Verifications")
