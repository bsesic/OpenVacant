from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
def test_data_export_requires_login(client):
    assert client.get(reverse("compliance:data_export")).status_code == 302


@pytest.mark.django_db
def test_data_export_returns_json(client, make_user):
    user = make_user(username="exp", email="exp@example.com")
    client.force_login(user)
    response = client.get(reverse("compliance:data_export"))
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert response.json()["user"]["email"] == "exp@example.com"


@pytest.mark.django_db
def test_account_delete_soft_deletes(client, make_user):
    user = make_user(username="del")
    client.force_login(user)
    response = client.post(reverse("compliance:account_delete"))
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.is_active is False
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
def test_purge_command_deletes_expired_accounts(make_user):
    expired = make_user(username="old")
    expired.deletion_requested_at = timezone.now() - timedelta(days=40)
    expired.save(update_fields=["deletion_requested_at"])
    keep = make_user(username="keep")

    call_command("purge_deleted_accounts")

    assert not User.objects.filter(pk=expired.pk).exists()
    assert User.objects.filter(pk=keep.pk).exists()


@pytest.mark.django_db
def test_sitemap_and_robots(client):
    sitemap = client.get(reverse("sitemap"))
    assert sitemap.status_code == 200
    assert b"/about/" in sitemap.content

    robots = client.get(reverse("robots"))
    assert robots.status_code == 200
    assert robots["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_contact_form_is_rate_limited(client):
    cache.clear()
    url = reverse("pages:contact")
    payload = {"name": "Sam", "email": "sam@example.com", "message": "Hi there"}
    statuses = [client.post(url, payload).status_code for _ in range(6)]
    assert statuses[-1] == 403
    assert statuses[0] in (200, 302)
