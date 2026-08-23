from django.contrib import admin
from unfold.admin import ModelAdmin

from billing.models import BillingAccount, ProcessedStripeEvent


@admin.register(BillingAccount)
class BillingAccountAdmin(ModelAdmin):
    list_display = ("organization", "plan", "status", "current_period_end", "updated_at")
    list_filter = ("status", "plan")
    search_fields = ("organization__name", "stripe_customer_id", "stripe_subscription_id")


@admin.register(ProcessedStripeEvent)
class ProcessedStripeEventAdmin(ModelAdmin):
    list_display = ("event_id", "event_type", "processed_at")
    search_fields = ("event_id", "event_type")
    readonly_fields = ("event_id", "event_type", "processed_at")
