from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from unfold.admin import ModelAdmin

from apps.parcels.models import Parcel


@admin.register(Parcel)
class ParcelAdmin(ModelAdmin, GISModelAdmin):
    list_display = (
        "parcel_number",
        "cadastral_district",
        "field_number",
        "area_sqm",
        "source",
    )
    list_filter = ("organization", "source")
    search_fields = ("parcel_number", "cadastral_district", "field_number", "source_reference")
    autocomplete_fields = ("organization",)
