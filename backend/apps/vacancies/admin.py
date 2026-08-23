from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.vacancies.models import VacancyPeriod


@admin.register(VacancyPeriod)
class VacancyPeriodAdmin(ModelAdmin):
    list_display = ("property", "status", "started_on", "ended_on", "recorded_by")
    list_filter = ("organization", "status")
    search_fields = ("property__reference", "source", "note")
    autocomplete_fields = ("organization", "property", "recorded_by")
    date_hierarchy = "started_on"
