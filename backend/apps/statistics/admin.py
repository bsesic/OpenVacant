from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.statistics.models import KeyFigureSnapshot


@admin.register(KeyFigureSnapshot)
class KeyFigureSnapshotAdmin(ModelAdmin):
    list_display = ("organization", "taken_on", "total_records", "confirmed_vacancies")
    list_filter = ("organization",)
    date_hierarchy = "taken_on"
    readonly_fields = ("figures",)
