from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FundingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.funding"
    label = "funding"
    verbose_name = _("Funding")
