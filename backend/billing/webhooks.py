"""Stripe webhook event handling. Pure logic — no HTTP — so it is easy to test."""

from datetime import datetime, timezone

from django.conf import settings

from billing.models import BillingAccount

SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def _plan_key_for_price(price_id):
    for plan in settings.STRIPE_PLANS:
        if plan["price_id"] and plan["price_id"] == price_id:
            return plan["key"]
    return ""


def _to_datetime(timestamp):
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def handle_event(event):
    """Apply a (already verified) Stripe event to the local billing state."""
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        account = BillingAccount.objects.filter(
            organization_id=obj.get("client_reference_id")
        ).first()
        if account:
            if obj.get("customer"):
                account.stripe_customer_id = obj["customer"]
            if obj.get("subscription"):
                account.stripe_subscription_id = obj["subscription"]
            account.save()

    elif event_type in SUBSCRIPTION_EVENTS:
        account = BillingAccount.objects.filter(stripe_customer_id=obj.get("customer")).first()
        if not account:
            return
        if event_type == "customer.subscription.deleted":
            account.status = "canceled"
        else:
            account.stripe_subscription_id = obj.get("id", account.stripe_subscription_id)
            account.status = obj.get("status", "")
            account.current_period_end = _to_datetime(obj.get("current_period_end"))
            items = (obj.get("items") or {}).get("data") or []
            if items:
                price_id = items[0].get("price", {}).get("id", "")
                account.plan = _plan_key_for_price(price_id) or account.plan
        account.save()
