from django.db import models
from django.utils.translation import gettext_lazy as _

from organizations.models import Organization

ACTIVE_STATUSES = {"active", "trialing"}


class BillingAccount(models.Model):
    """Stripe billing state for an organization (the subscription lives on the org)."""

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="billing"
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    plan = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Billing for {self.organization}"

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES


class ProcessedStripeEvent(models.Model):
    """Records handled webhook event ids so retries are idempotent."""

    event_id = models.CharField(_("event id"), max_length=255, unique=True)
    event_type = models.CharField(max_length=100, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id
