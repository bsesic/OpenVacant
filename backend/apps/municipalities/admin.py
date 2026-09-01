from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.municipalities.models import District, ModuleActivation, Municipality


class ModuleActivationInline(admin.TabularInline):
    model = ModuleActivation
    extra = 0
    fields = ("module", "enabled")


class DistrictInline(admin.TabularInline):
    model = District
    extra = 0
    fields = ("name", "kind", "code")
    show_change_link = True


@admin.register(Municipality)
class MunicipalityAdmin(ModelAdmin, GISModelAdmin):
    list_display = ("name", "kind", "state", "municipality_key", "domain")
    list_filter = ("kind", "state")
    search_fields = ("name", "official_name", "municipality_key", "domain")
    autocomplete_fields = ("organization",)
    inlines = (DistrictInline, ModuleActivationInline)
    fieldsets = (
        (None, {"fields": ("organization", "kind")}),
        (
            _("Identity"),
            {
                "fields": (
                    "name",
                    "official_name",
                    "municipality_key",
                    "state",
                    "district_name",
                )
            },
        ),
        (
            _("Contact"),
            {"fields": ("contact_email", "contact_phone", "postal_address", "website")},
        ),
        (_("Geography"), {"fields": ("centre", "boundary", "default_zoom")}),
        (
            _("White label"),
            {
                "fields": (
                    "domain",
                    "logo",
                    "coat_of_arms",
                    "primary_colour",
                    "accent_colour",
                    "font_family",
                )
            },
        ),
        (_("Public presentation"), {"fields": ("public_intro",)}),
        (_("Legal texts"), {"fields": ("imprint", "privacy_notice", "terms")}),
    )


@admin.register(District)
class DistrictAdmin(ModelAdmin, GISModelAdmin):
    list_display = ("name", "municipality", "kind", "code")
    list_filter = ("municipality", "kind")
    search_fields = ("name", "code")
    autocomplete_fields = ("municipality",)


@admin.register(ModuleActivation)
class ModuleActivationAdmin(ModelAdmin):
    list_display = ("municipality", "module", "enabled", "changed_at")
    list_filter = ("municipality", "module", "enabled")
