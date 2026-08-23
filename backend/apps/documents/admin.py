from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.documents.models import PropertyDocument


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(ModelAdmin):
    list_display = ("title", "property", "kind", "visibility", "uploaded_by", "uploaded_at")
    list_filter = ("organization", "kind", "visibility")
    search_fields = ("title", "description", "property__reference")
    autocomplete_fields = ("organization", "property", "uploaded_by")
    date_hierarchy = "uploaded_at"
