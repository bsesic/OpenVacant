import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    ["home", "about", "faq", "imprint", "privacy", "terms", "contact"],
)
def test_static_pages_render(client, name):
    response = client.get(reverse(f"pages:{name}"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_contact_form_submits(client):
    response = client.post(
        reverse("pages:contact"),
        {"name": "Sam", "email": "sam@example.com", "message": "Hello there"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_set_language(client):
    response = client.post(reverse("set_language"), {"language": "de", "next": "/"})
    assert response.status_code == 302
