from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.owners.models import Owner, Ownership, OwnerInterest, OwnershipClaim


@admin.register(Owner)
class OwnerAdmin(ModelAdmin):
    list_display = ("name", "kind", "contact_state", "organization")
    list_filter = ("organization", "kind", "contact_state")
    search_fields = ("name", "representative", "email")
    autocomplete_fields = ("organization",)


@admin.register(Ownership)
class OwnershipAdmin(ModelAdmin):
    list_display = ("owner", "property", "share", "recorded_on")
    list_filter = ("organization",)
    search_fields = ("owner__name", "property__reference")
    autocomplete_fields = ("organization", "owner", "property")


@admin.register(OwnershipClaim)
class OwnershipClaimAdmin(ModelAdmin):
    list_display = ("claimant", "property", "status", "reviewed_by", "created_at")
    list_filter = ("organization", "status")
    search_fields = ("claimant__username", "property__reference")
    autocomplete_fields = ("organization", "property", "claimant", "owner")
    readonly_fields = ("reviewed_by", "reviewed_at")


@admin.register(OwnerInterest)
class OwnerInterestAdmin(ModelAdmin):
    list_display = ("property", "owner", "kind", "stated_on")
    list_filter = ("organization", "kind")
    search_fields = ("property__reference", "owner__name")
    autocomplete_fields = ("organization", "property", "owner", "recorded_by")
