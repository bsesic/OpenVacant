from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MunicipalitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.municipalities"
    label = "municipalities"
    verbose_name = _("Municipalities")
