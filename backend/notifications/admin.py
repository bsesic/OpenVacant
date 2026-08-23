from django.contrib import admin
from unfold.admin import ModelAdmin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("recipient", "verb", "organization", "unread", "created_at")
    list_filter = ("unread",)
    search_fields = ("recipient__username", "verb")
