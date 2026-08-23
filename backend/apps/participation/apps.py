from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ParticipationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.participation"
    label = "participation"
    verbose_name = _("Participation")
