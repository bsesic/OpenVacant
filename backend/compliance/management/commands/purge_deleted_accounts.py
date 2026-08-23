from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Hard-delete users who requested deletion more than N days ago (GDPR)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=getattr(settings, "ACCOUNT_DELETION_GRACE_DAYS", 30),
            help="Grace period in days before a deactivated account is purged.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        User = get_user_model()
        queryset = User.objects.filter(
            deletion_requested_at__isnull=False, deletion_requested_at__lte=cutoff
        )
        count = queryset.count()
        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {count} account(s)."))
