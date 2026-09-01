from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.heritage.models import HeritageCheck, MonumentRecord


@admin.register(MonumentRecord)
class MonumentRecordAdmin(ModelAdmin):
    list_display = ("designation", "monument_id", "scope", "authority", "property")
    list_filter = ("organization", "scope")
    search_fields = ("designation", "monument_id", "authority")
    autocomplete_fields = ("organization", "property")


@admin.register(HeritageCheck)
class HeritageCheckAdmin(ModelAdmin):
    list_display = ("property", "result", "checked_on", "checked_by", "authority_reference")
    list_filter = ("organization", "result")
    search_fields = ("property__reference", "authority_reference", "note")
    autocomplete_fields = ("organization", "property", "checked_by", "monument")
    date_hierarchy = "checked_on"
