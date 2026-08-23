import pytest
from django.core import mail
from django.urls import reverse

from newsletter.models import Subscriber


@pytest.mark.django_db
def test_subscribe_creates_unconfirmed_and_sends_email(client):
    response = client.post(reverse("newsletter:subscribe"), {"email": "fan@example.com"})
    assert response.status_code == 302
    sub = Subscriber.objects.get(email="fan@example.com")
    assert sub.confirmed is False
    assert len(mail.outbox) == 1
    assert "confirm" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
def test_confirm_sets_confirmed(client):
    sub = Subscriber.objects.create(email="fan@example.com")
    response = client.get(reverse("newsletter:confirm", args=[sub.token]))
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.confirmed is True
    assert sub.is_active is True


@pytest.mark.django_db
def test_unsubscribe_sets_timestamp(client):
    sub = Subscriber.objects.create(email="fan@example.com", confirmed=True)
    response = client.get(reverse("newsletter:unsubscribe", args=[sub.token]))
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.unsubscribed_at is not None
    assert sub.is_active is False
