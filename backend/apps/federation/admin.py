from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.federation.models import PeerInstance, ShareScope, SyncRun


class ShareScopeInline(admin.TabularInline):
    model = ShareScope
    extra = 0
    fields = ("category", "direction", "is_enabled")


@admin.register(PeerInstance)
class PeerInstanceAdmin(ModelAdmin):
    list_display = ("name", "level", "base_url", "is_active")
    list_filter = ("organization", "level", "is_active")
    search_fields = ("name", "base_url")
    autocomplete_fields = ("organization",)
    inlines = (ShareScopeInline,)


@admin.register(SyncRun)
class SyncRunAdmin(ModelAdmin):
    list_display = ("peer", "direction", "category", "status", "started_at", "record_count")
    list_filter = ("status", "direction", "category")
    readonly_fields = ("peer", "direction", "category", "started_at", "finished_at")

    def has_add_permission(self, request):
        # Runs are written by the synchronisation, never by hand.
        return False
