import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from notifications.models import notify


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
def test_me_requires_auth(api):
    assert api.get(reverse("v1:me")).status_code in (401, 403)


@pytest.mark.django_db
def test_me_get_and_patch(api, make_user):
    user = make_user(username="apiuser")
    api.force_authenticate(user)
    assert api.get(reverse("v1:me")).json()["username"] == "apiuser"
    response = api.patch(reverse("v1:me"), {"first_name": "Api"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Api"


@pytest.mark.django_db
def test_notifications_api_list_and_read(api, make_user):
    user = make_user(username="apinote")
    note = notify(user, "Hello API")
    api.force_authenticate(user)
    assert api.get(reverse("v1:notification-list")).json()["count"] == 1
    response = api.post(reverse("v1:notification-read", args=[note.pk]))
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.unread is False


@pytest.mark.django_db
def test_schema_and_docs(client):
    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("swagger-ui")).status_code == 200
