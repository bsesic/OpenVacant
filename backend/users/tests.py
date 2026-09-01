import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_user_factory_creates_user(make_user):
    user = make_user()
    assert user.pk is not None
    assert user.check_password("testpass123")


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_home_page_renders(client):
    response = client.get(reverse("pages:home"))
    assert response.status_code == 200


# --- API profile (v1) ------------------------------------------------------
@pytest.mark.django_db
def test_profile_api_requires_authentication(client):
    response = client.get(reverse("v1:me"))
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_profile_api_returns_username(client, make_user):
    user = make_user(username="alice")
    client.force_login(user)
    response = client.get(reverse("v1:me"))
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


# --- allauth flows ---------------------------------------------------------
@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_sends_verification_email(client):
    response = client.post(
        reverse("account_signup"),
        {
            "username": "bob",
            "email": "bob@example.com",
            "password1": "sup3r-s3cret-pw",
            "password2": "sup3r-s3cret-pw",
        },
    )
    assert response.status_code in (200, 302)
    assert User.objects.filter(username="bob").exists()
    # Mandatory verification: a confirmation email is sent on signup.
    assert len(mail.outbox) == 1


# --- profile (web) ---------------------------------------------------------
@pytest.mark.django_db
def test_profile_page_requires_login(client):
    response = client.get(reverse("profile"))
    assert response.status_code == 302
    assert reverse("account_login") in response.url


@pytest.mark.django_db
def test_profile_page_renders_for_logged_in_user(client, make_user):
    client.force_login(make_user(username="carol"))
    response = client.get(reverse("profile"))
    assert response.status_code == 200
    assert b"carol" in response.content


@pytest.mark.django_db
def test_profile_edit_updates_name(client, make_user):
    user = make_user(username="dave")
    client.force_login(user)
    response = client.post(
        reverse("profile_edit"),
        {"first_name": "Dave", "last_name": "Doe"},
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.first_name == "Dave"
    assert user.last_name == "Doe"


@pytest.mark.django_db
def test_login_notification_sent_on_login(client, make_user):
    mail.outbox.clear()
    client.force_login(make_user(username="erin", email="erin@example.com"))
    assert any("sign-in" in m.subject.lower() for m in mail.outbox)
