from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HeritageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.heritage"
    label = "heritage"
    verbose_name = _("Heritage protection")
