"""Import a GeoJSON file as a geodata layer.

Layers arrive as files from state and municipal portals, so a repeatable command
is the honest interface. A repeated import of the same key replaces the layer's
features rather than piling up duplicates.
"""

import json

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.geodata.models import GeoFeature, GeoLayer, LayerCategory
from apps.municipalities.models import Municipality


class Command(BaseCommand):
    help = "Import a GeoJSON file as a geodata layer for one municipality."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the GeoJSON file.")
        parser.add_argument(
            "--municipality",
            required=True,
            help="Municipality key or exact name of the owning municipality.",
        )
        parser.add_argument("--name", required=True, help="Human-readable layer name.")
        parser.add_argument(
            "--slug",
            help="Stable key for the layer. Defaults to a slug of the name.",
        )
        parser.add_argument(
            "--category",
            default=LayerCategory.OTHER,
            choices=[choice.value for choice in LayerCategory],
            help="What the layer means, which decides the context flag it drives.",
        )
        parser.add_argument("--source", default="", help="Where the data came from.")
        parser.add_argument("--source-url", default="", help="URL of the source.")
        parser.add_argument("--licence", default="", help="Licence of the data.")
        parser.add_argument(
            "--name-property",
            default="name",
            help="Feature property to use as the feature name.",
        )
        parser.add_argument(
            "--id-property",
            default="id",
            help="Feature property to use as the external id.",
        )
        parser.add_argument(
            "--public",
            action="store_true",
            help="Allow this layer to be shown on the public map.",
        )
        parser.add_argument(
            "--refresh-context",
            action="store_true",
            help="Recompute the spatial context of the municipality's records afterwards.",
        )

    def handle(self, *args, **options):
        municipality = self._resolve_municipality(options["municipality"])
        payload = self._read(options["path"])
        features = payload.get("features")
        if not features:
            raise CommandError("The file contains no features.")

        slug = options["slug"] or slugify(options["name"])
        with transaction.atomic():
            layer, created = GeoLayer.objects.update_or_create(
                organization=municipality.organization,
                slug=slug,
                defaults={
                    "name": options["name"],
                    "category": options["category"],
                    "source": options["source"],
                    "source_url": options["source_url"],
                    "licence": options["licence"],
                    "is_public": options["public"],
                    "imported_at": timezone.now(),
                },
            )
            # Replace rather than merge: a partial layer would silently give the
            # wrong answer for every object in the missing part.
            removed = layer.features.count()
            layer.features.all().delete()

            imported, skipped = self._import_features(layer, features, options)

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Replaced'} layer “{layer.name}” "
                f"({layer.get_category_display()}): {imported} features imported, "
                f"{removed} replaced, {skipped} skipped."
            )
        )

        if options["refresh_context"]:
            self._refresh_context(municipality)

    def _import_features(self, layer, features, options):
        imported = 0
        skipped = 0
        for entry in features:
            geometry_data = entry.get("geometry")
            if not geometry_data:
                skipped += 1
                continue
            try:
                geometry = GEOSGeometry(json.dumps(geometry_data), srid=4326)
            except (ValueError, TypeError):
                skipped += 1
                continue
            attributes = entry.get("properties") or {}
            GeoFeature.objects.create(
                layer=layer,
                name=str(attributes.get(options["name_property"], ""))[:255],
                external_id=str(
                    attributes.get(options["id_property"], entry.get("id", ""))
                )[:255],
                geometry=geometry,
                attributes=attributes,
            )
            imported += 1
        return imported, skipped

    def _refresh_context(self, municipality):
        from apps.geodata.services import refresh_context_for_queryset
        from apps.properties.models import Property

        records = Property.objects.filter(organization=municipality.organization)
        changed = refresh_context_for_queryset(records)
        self.stdout.write(
            self.style.SUCCESS(f"Spatial context recomputed; {changed} records changed.")
        )

    @staticmethod
    def _read(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError as error:
            raise CommandError(f"File not found: {path}") from error
        except json.JSONDecodeError as error:
            raise CommandError(f"Not valid JSON: {error}") from error

    @staticmethod
    def _resolve_municipality(identifier):
        municipality = Municipality.objects.filter(
            municipality_key=identifier
        ).first() or Municipality.objects.filter(name=identifier).first()
        if municipality is None:
            raise CommandError(f"No municipality with key or name “{identifier}”.")
        return municipality
