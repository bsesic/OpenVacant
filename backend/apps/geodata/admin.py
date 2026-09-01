from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from unfold.admin import ModelAdmin

from apps.geodata.models import GeoFeature, GeoLayer, SpatialContext


@admin.register(GeoLayer)
class GeoLayerAdmin(ModelAdmin):
    list_display = (
        "name",
        "category",
        "feature_count",
        "is_active",
        "is_public",
        "imported_at",
    )
    list_filter = ("organization", "category", "is_active", "is_public")
    search_fields = ("name", "slug", "source")
    autocomplete_fields = ("organization",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("imported_at",)


@admin.register(GeoFeature)
class GeoFeatureAdmin(ModelAdmin, GISModelAdmin):
    list_display = ("name", "layer", "external_id")
    list_filter = ("layer__category", "layer")
    search_fields = ("name", "external_id")
    autocomplete_fields = ("layer",)


@admin.register(SpatialContext)
class SpatialContextAdmin(ModelAdmin):
    list_display = ("property", "feature", "matched_at")
    list_filter = ("feature__layer__category",)
    search_fields = ("property__reference", "feature__name")
    autocomplete_fields = ("property", "feature")

    def has_add_permission(self, request):
        # Context is derived from the layers, never typed in.
        return False
