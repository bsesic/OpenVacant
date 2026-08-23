import json

import pytest
from django.urls import reverse

from billing import services
from billing.models import BillingAccount, ProcessedStripeEvent
from organizations.models import Role


@pytest.mark.django_db
def test_pricing_page_renders(client):
    response = client.get(reverse("billing:pricing"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_billing_page_requires_manager(client, make_member):
    # Anonymous -> redirect to login.
    assert client.get(reverse("billing:billing")).status_code == 302

    # Member (non-manager) of the tenant cannot manage its subscription...
    owner, org = make_member(username="bowner")
    member, _ = make_member(role=Role.MEMBER, organization=org, username="bmember")
    # Make that org the member's active org via switch.
    client.force_login(member)
    client.post(reverse("organizations:switch", args=[org.pk]))
    assert client.get(reverse("billing:billing")).status_code == 403

    # Owner can.
    client.force_login(owner)
    assert client.get(reverse("billing:billing")).status_code == 200


@pytest.mark.django_db
def test_checkout_redirects_to_stripe(client, make_member, monkeypatch, settings):
    settings.BILLING_ENABLED = True
    settings.STRIPE_PLANS = [
        {"key": "pro", "name": "Pro", "description": "", "price_id": "price_123"}
    ]
    monkeypatch.setattr(
        services,
        "create_checkout_session",
        lambda account, price_id, success_url, cancel_url: {"url": "https://stripe.test/checkout"},
    )
    owner, _org = make_member(username="cowner")
    client.force_login(owner)
    response = client.post(reverse("billing:checkout"), {"plan": "pro"})
    assert response.status_code == 302
    assert response.url == "https://stripe.test/checkout"


@pytest.mark.django_db
def test_checkout_disabled_without_config(client, make_member, settings):
    settings.BILLING_ENABLED = False
    owner, _org = make_member(username="downer")
    client.force_login(owner)
    response = client.post(reverse("billing:checkout"), {"plan": "pro"})
    assert response.status_code == 302
    assert response.url == reverse("billing:pricing")


def _fake_event(event_id, event_type, obj):
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


@pytest.mark.django_db
def test_webhook_is_idempotent(client, make_member, monkeypatch):
    _owner, org = make_member(username="wowner")
    account = BillingAccount.objects.create(organization=org, stripe_customer_id="cus_1")
    event = _fake_event(
        "evt_1",
        "checkout.session.completed",
        {"client_reference_id": str(org.pk), "customer": "cus_1", "subscription": "sub_1"},
    )
    monkeypatch.setattr(services, "construct_event", lambda payload, sig: event)

    url = reverse("billing:webhook")
    for _ in range(2):
        response = client.post(
            url,
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig",
        )
        assert response.status_code == 200

    assert ProcessedStripeEvent.objects.filter(event_id="evt_1").count() == 1
    account.refresh_from_db()
    assert account.stripe_subscription_id == "sub_1"


@pytest.mark.django_db
def test_webhook_updates_subscription_status(client, make_member, monkeypatch):
    _owner, org = make_member(username="sowner")
    account = BillingAccount.objects.create(organization=org, stripe_customer_id="cus_2")
    event = _fake_event(
        "evt_2",
        "customer.subscription.updated",
        {
            "id": "sub_2",
            "customer": "cus_2",
            "status": "active",
            "current_period_end": 1893456000,
            "items": {"data": [{"price": {"id": "price_123"}}]},
        },
    )
    monkeypatch.setattr(services, "construct_event", lambda payload, sig: event)
    client.post(
        reverse("billing:webhook"),
        data="{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="sig",
    )
    account.refresh_from_db()
    assert account.status == "active"
    assert account.is_active


@pytest.mark.django_db
def test_webhook_rejects_bad_signature(client, monkeypatch):
    def boom(payload, sig):
        raise ValueError("bad sig")

    monkeypatch.setattr(services, "construct_event", boom)
    response = client.post(
        reverse("billing:webhook"),
        data="{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="bad",
    )
    assert response.status_code == 400
