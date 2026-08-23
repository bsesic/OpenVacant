"""Store the current key figures as a snapshot."""

from django.core.management.base import BaseCommand, CommandError

from apps.municipalities.models import Municipality
from apps.statistics.services import take_snapshot


class Command(BaseCommand):
    help = "Store today's key figures for one municipality or for all of them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--municipality",
            help="Municipality key or exact name. Default: all municipalities.",
        )

    def handle(self, *args, **options):
        municipalities = Municipality.objects.select_related("organization")
        identifier = options.get("municipality")
        if identifier:
            municipality = municipalities.filter(
                municipality_key=identifier
            ).first() or municipalities.filter(name=identifier).first()
            if municipality is None:
                raise CommandError(f"No municipality with key or name “{identifier}”.")
            municipalities = [municipality]

        for municipality in municipalities:
            snapshot = take_snapshot(municipality.organization)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{municipality.name}: {snapshot.total_records} records, "
                    f"{snapshot.confirmed_vacancies} confirmed vacancies "
                    f"({snapshot.taken_on})."
                )
            )
