"""Recompute the spatial context of property records.

Run after importing or deactivating a layer: the flags on a record are a cached
answer, and a layer change makes that answer stale.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.geodata.services import refresh_context_for_queryset
from apps.municipalities.models import Municipality
from apps.properties.models import Property


class Command(BaseCommand):
    help = "Recompute the spatial context flags of property records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--municipality",
            help="Restrict to one municipality (key or exact name). Default: all.",
        )

    def handle(self, *args, **options):
        records = Property.objects.all()
        identifier = options.get("municipality")
        if identifier:
            municipality = Municipality.objects.filter(
                municipality_key=identifier
            ).first() or Municipality.objects.filter(name=identifier).first()
            if municipality is None:
                raise CommandError(f"No municipality with key or name “{identifier}”.")
            records = records.filter(organization=municipality.organization)

        total = records.count()
        changed = refresh_context_for_queryset(records)
        self.stdout.write(
            self.style.SUCCESS(f"{total} records checked, {changed} changed.")
        )
