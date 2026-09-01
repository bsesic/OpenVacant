from django.contrib import admin
from unfold.admin import ModelAdmin

from newsletter.models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(ModelAdmin):
    list_display = ("email", "confirmed", "subscribed_at", "unsubscribed_at")
    list_filter = ("confirmed",)
    search_fields = ("email",)
    readonly_fields = ("token", "subscribed_at")
