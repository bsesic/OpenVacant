from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.participation.models import Award, Badge, ContributorProfile, PointEntry


class PointEntryInline(admin.TabularInline):
    model = PointEntry
    extra = 0
    fields = ("reason", "points", "note", "awarded_by", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class AwardInline(admin.TabularInline):
    model = Award
    extra = 0
    fields = ("badge", "awarded_at")
    readonly_fields = ("awarded_at",)


@admin.register(ContributorProfile)
class ContributorProfileAdmin(ModelAdmin):
    list_display = (
        "user",
        "organization",
        "points",
        "level",
        "reports_accepted",
        "reports_confirmed",
        "inspections_completed",
    )
    list_filter = ("organization", "level", "wants_recognition")
    search_fields = ("user__username", "user__email", "display_name")
    autocomplete_fields = ("organization", "user")
    readonly_fields = (
        "points",
        "level",
        "reports_accepted",
        "reports_confirmed",
        "inspections_completed",
        "tasks_completed",
    )
    inlines = (AwardInline, PointEntryInline)


@admin.register(Badge)
class BadgeAdmin(ModelAdmin):
    list_display = (
        "name",
        "key",
        "required_points",
        "required_confirmed_reports",
        "required_inspections",
        "is_active",
    )
    search_fields = ("name", "key")
    prepopulated_fields = {"key": ("name",)}
