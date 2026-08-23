from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reports"
    label = "reports"
    verbose_name = _("Citizen reports")

    def ready(self):
        # Reports are personal data when a submitter identifies themselves, so
        # they belong in the GDPR export.
        from apps.reports.exporters import collect_reports
        from compliance.exporters import register_export_collector

        register_export_collector(collect_reports)
