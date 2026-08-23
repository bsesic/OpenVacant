"""Apply the retention rules.

Run on a schedule. Reports the effect of each rule so the deletion concept can
be evidenced rather than asserted.
"""

from django.core.management.base import BaseCommand

from compliance import retention


class Command(BaseCommand):
    help = "Apply the data retention rules (deletion and anonymisation)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what the rules would affect without changing anything.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            self._report_dry_run()
            return
        results = retention.run_all()
        for rule, count in results.items():
            self.stdout.write(self.style.SUCCESS(f"{rule}: {count}"))

    def _report_dry_run(self):
        import datetime

        from django.conf import settings
        from django.utils import timezone

        from apps.reports.models import DISCARDED_REPORT_STATUSES, Report
        from compliance.models import AccessLog

        def cutoff(days):
            return timezone.now() - datetime.timedelta(days=days)

        counts = {
            "discarded_reports_deleted": Report.objects.filter(
                status__in=DISCARDED_REPORT_STATUSES,
                updated_at__lt=cutoff(settings.REPORT_REJECTED_RETENTION_DAYS),
                property__isnull=True,
            ).count(),
            "report_origins_anonymised": Report.objects.filter(
                submitted_from_ip__isnull=False, created_at__lt=cutoff(30)
            ).count(),
            "access_log_entries_deleted": AccessLog.objects.filter(
                created_at__lt=cutoff(settings.AUDIT_LOG_RETENTION_DAYS)
            ).count(),
        }
        for rule, count in counts.items():
            self.stdout.write(f"{rule}: {count} (dry run)")
