from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.integrations.models import ApiClient


@admin.register(ApiClient)
class ApiClientAdmin(ModelAdmin):
    list_display = (
        "name",
        "organization",
        "key_prefix",
        "is_active",
        "expires_at",
        "last_used_at",
        "request_count",
    )
    list_filter = ("organization", "is_active")
    search_fields = ("name", "description", "contact_email", "key_prefix")
    autocomplete_fields = ("organization", "created_by")
    # The key hash is never edited, and the plaintext key does not exist here.
    readonly_fields = (
        "key_prefix",
        "key_hash",
        "last_used_at",
        "request_count",
        "revoked_at",
    )
