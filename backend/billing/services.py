"""Thin wrapper around the Stripe API.

All Stripe network calls live here so views stay testable (mock this module).
"""

import stripe
from django.conf import settings


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def ensure_customer(billing_account):
    """Return the Stripe customer id for the org, creating the customer if needed."""
    if billing_account.stripe_customer_id:
        return billing_account.stripe_customer_id
    customer = _client().Customer.create(
        name=billing_account.organization.name,
        metadata={"organization_id": billing_account.organization_id},
    )
    billing_account.stripe_customer_id = customer["id"]
    billing_account.save(update_fields=["stripe_customer_id", "updated_at"])
    return customer["id"]


def create_checkout_session(billing_account, price_id, success_url, cancel_url):
    customer_id = ensure_customer(billing_account)
    return _client().checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(billing_account.organization_id),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        automatic_tax={"enabled": settings.STRIPE_TAX_ENABLED},
    )


def create_portal_session(billing_account, return_url):
    return _client().billing_portal.Session.create(
        customer=billing_account.stripe_customer_id,
        return_url=return_url,
    )


def construct_event(payload, sig_header):
    """Verify and parse a webhook payload using the signing secret."""
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
