from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class VacanciesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vacancies"
    label = "vacancies"
    verbose_name = _("Vacancy history")
