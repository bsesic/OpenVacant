from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.inspections.models import Inspection, InspectionPhoto


class InspectionPhotoInline(admin.TabularInline):
    model = InspectionPhoto
    extra = 0
    fields = ("image", "caption", "is_public")


@admin.register(Inspection)
class InspectionAdmin(ModelAdmin):
    list_display = (
        "property",
        "kind",
        "result",
        "inspected_on",
        "inspector",
        "inspector_role",
        "applied_at",
    )
    list_filter = ("organization", "kind", "result")
    search_fields = ("property__reference", "findings")
    autocomplete_fields = ("organization", "property", "inspector")
    inlines = (InspectionPhotoInline,)
    readonly_fields = ("inspector_role", "applied_at")
    date_hierarchy = "inspected_on"
