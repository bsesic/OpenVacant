from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.workflows.models import Task


@admin.register(Task)
class TaskAdmin(ModelAdmin):
    list_display = (
        "label",
        "task_type",
        "status",
        "priority",
        "assignee",
        "due_on",
        "property",
    )
    list_filter = ("organization", "status", "task_type", "priority")
    search_fields = ("title", "description", "property__reference")
    autocomplete_fields = ("organization", "property", "report", "assignee", "created_by")
    date_hierarchy = "created_at"
