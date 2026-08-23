from django.contrib import admin
from unfold.admin import ModelAdmin

from compliance.models import AccessLog, ConsentRecord


@admin.register(AccessLog)
class AccessLogAdmin(ModelAdmin):
    list_display = ("created_at", "actor_label", "category", "object_reference", "organization")
    list_filter = ("category", "organization")
    search_fields = ("actor_label", "object_reference", "purpose")
    date_hierarchy = "created_at"
    # The log is evidence. It is written by the application and read here.
    readonly_fields = (
        "organization",
        "actor",
        "actor_label",
        "category",
        "object_reference",
        "purpose",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ConsentRecord)
class ConsentRecordAdmin(ModelAdmin):
    list_display = ("subject", "purpose", "granted_at", "withdrawn_at", "source")
    list_filter = ("purpose", "source")
    search_fields = ("subject_label", "user__username", "user__email")
    date_hierarchy = "granted_at"
    readonly_fields = ("granted_at", "source", "policy_version")
