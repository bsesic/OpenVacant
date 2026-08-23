from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from unfold.admin import ModelAdmin

from apps.reports.models import Report, ReportPhoto


class ReportPhotoInline(admin.TabularInline):
    model = ReportPhoto
    extra = 0
    fields = ("image", "caption", "is_public")


@admin.register(Report)
class ReportAdmin(ModelAdmin, GISModelAdmin):
    list_display = (
        "reference",
        "category",
        "status",
        "address_line",
        "property",
        "created_at",
    )
    list_filter = ("organization", "status", "category")
    search_fields = ("reference", "description", "street", "city", "contact_email")
    autocomplete_fields = ("organization", "property", "district", "submitted_by")
    inlines = (ReportPhotoInline,)
    readonly_fields = (
        "reference",
        "consent_given_at",
        "submitted_from_ip",
        "moderated_by",
        "moderated_at",
    )
    date_hierarchy = "created_at"
