from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.funding.models import FundingProgramme, PropertyFunding


@admin.register(FundingProgramme)
class FundingProgrammeAdmin(ModelAdmin):
    list_display = ("name", "provider", "level", "starts_on", "ends_on", "is_active")
    list_filter = ("organization", "level", "is_active")
    search_fields = ("name", "provider")
    autocomplete_fields = ("organization",)


@admin.register(PropertyFunding)
class PropertyFundingAdmin(ModelAdmin):
    list_display = ("property", "programme", "status", "amount", "reference")
    list_filter = ("organization", "status")
    search_fields = ("property__reference", "programme__name", "reference")
    autocomplete_fields = ("organization", "property", "programme", "updated_by")
