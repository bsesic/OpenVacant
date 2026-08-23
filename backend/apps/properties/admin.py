from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm

from apps.properties.models import Property, PropertyDamage, StatusTransition


class PropertyDamageInline(admin.TabularInline):
    model = PropertyDamage
    extra = 0
    fields = ("damage_type", "severity", "source", "note")


class StatusTransitionInline(admin.TabularInline):
    model = StatusTransition
    extra = 0
    can_delete = False
    fields = ("from_status", "to_status", "actor", "reason", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        # The audit trail is written by the workflow, never typed in.
        return False


@admin.register(Property)
class PropertyAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin, GISModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm
    list_display = (
        "reference",
        "address_line",
        "district",
        "property_type",
        "status",
        "vacancy_status",
        "condition",
        "priority",
        "is_public",
    )
    list_filter = (
        "organization",
        "status",
        "vacancy_status",
        "condition",
        "priority",
        "property_type",
        "is_public",
        "is_heritage_protected",
        "in_redevelopment_area",
    )
    search_fields = ("reference", "street", "city", "postal_code", "public_description")
    autocomplete_fields = ("organization", "district", "created_by")
    filter_horizontal = ("parcels",)
    inlines = (PropertyDamageInline, StatusTransitionInline)
    # The workflow status changes through transitions so the audit trail stays
    # complete; editing it directly here would bypass that.
    readonly_fields = ("reference", "status", "context_updated_at")
    fieldsets = (
        (None, {"fields": ("organization", "reference", "district")}),
        (
            _("Address"),
            {
                "fields": (
                    "street",
                    "house_number",
                    "postal_code",
                    "city",
                    "address_note",
                    "location",
                )
            },
        ),
        (_("Classification"), {"fields": ("property_type", "last_known_use")}),
        (
            _("State"),
            {
                "fields": (
                    "status",
                    "vacancy_status",
                    "condition",
                    "condition_source",
                    "priority",
                    "recorded_on",
                    "last_checked_on",
                )
            },
        ),
        (
            _("Descriptions"),
            {"fields": ("public_description", "internal_description", "sources")},
        ),
        (_("Publication"), {"fields": ("is_public",)}),
        (
            _("Professional data"),
            {
                "fields": (
                    "parcels",
                    "plot_area_sqm",
                    "usable_area_sqm",
                    "living_area_sqm",
                    "year_built",
                    "units_total",
                    "units_vacant",
                )
            },
        ),
        (
            _("Spatial context"),
            {
                "fields": (
                    "is_heritage_protected",
                    "in_redevelopment_area",
                    "in_funding_area",
                    "in_development_area",
                    "context_updated_at",
                )
            },
        ),
        (_("Record"), {"fields": ("created_by",)}),
    )


@admin.register(StatusTransition)
class StatusTransitionAdmin(ModelAdmin):
    list_display = ("property", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
    search_fields = ("property__reference", "reason")
    readonly_fields = ("property", "from_status", "to_status", "actor", "reason", "note")

    def has_add_permission(self, request):
        return False
