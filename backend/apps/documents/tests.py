import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.documents.models import DocumentKind, PropertyDocument, Visibility
from apps.properties.models import Property
from organizations.models import Role


@pytest.fixture
def _media(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def setup(municipal_staff, _media):
    user, organization, municipality = municipal_staff(username="doc_staff")
    record = Property.objects.create(
        organization=organization, street="Poststraße", city="Reichenbach"
    )
    return user, organization, municipality, record


def _file(name="a.pdf", content=b"data"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


def _document(organization, record, **extra):
    return PropertyDocument.objects.create(
        organization=organization,
        property=record,
        title=extra.pop("title", "A file"),
        kind=extra.pop("kind", DocumentKind.PHOTO),
        file=_file(),
        **extra,
    )


# --- Visibility ------------------------------------------------------------


@pytest.mark.django_db
def test_documents_are_internal_by_default(setup):
    _user, organization, _municipality, record = setup
    document = _document(organization, record)
    assert document.visibility == Visibility.INTERNAL
    assert document.is_public is False


@pytest.mark.django_db
def test_a_released_document_stays_hidden_while_the_record_is_not_published(setup):
    _user, organization, _municipality, record = setup
    document = _document(organization, record, visibility=Visibility.PUBLIC)
    # Publishing the photo of an unpublished object would disclose the object.
    assert record.is_public is False
    assert document.is_public is False

    record.is_public = True
    record.save(update_fields=["is_public"])
    document.refresh_from_db()
    assert document.is_public is True


@pytest.mark.django_db
def test_the_public_queryset_requires_both_releases(setup):
    _user, organization, _municipality, record = setup
    _document(organization, record, title="Internal photo")
    released = _document(organization, record, title="Released", visibility=Visibility.PUBLIC)

    scoped = PropertyDocument.objects.for_organization(organization)
    assert scoped.public().count() == 0

    record.is_public = True
    record.save(update_fields=["is_public"])
    assert list(scoped.public()) == [released]
    assert scoped.internal().count() == 1


@pytest.mark.django_db
def test_sensitive_kinds_cannot_be_published_even_by_setting_the_field(setup):
    _user, organization, _municipality, record = setup
    record.is_public = True
    record.save(update_fields=["is_public"])

    for kind in (
        DocumentKind.CORRESPONDENCE,
        DocumentKind.LAND_REGISTRY,
        DocumentKind.EXPERT_REPORT,
    ):
        document = _document(
            organization, record, kind=kind, visibility=Visibility.PUBLIC, title=str(kind)
        )
        # The model refuses, so an import or a shell session cannot leak a letter.
        assert document.visibility == Visibility.INTERNAL
        assert document.can_be_published is False
        assert document.is_public is False


@pytest.mark.django_db
def test_the_form_rejects_publishing_a_sensitive_kind(setup):
    from apps.documents.forms import PropertyDocumentForm

    form = PropertyDocumentForm(
        data={
            "kind": DocumentKind.CORRESPONDENCE.value,
            "title": "Letter to the owner",
            "visibility": Visibility.PUBLIC.value,
        },
        files={"file": _file()},
    )
    assert not form.is_valid()
    assert "visibility" in form.errors


# --- Views -----------------------------------------------------------------


@pytest.mark.django_db
def test_staff_can_upload_a_document(client, setup):
    user, organization, _municipality, record = setup
    client.force_login(user)
    response = client.post(
        reverse("documents:create", args=[record.pk]),
        {
            "kind": DocumentKind.SITE_PLAN.value,
            "title": "Site plan 2026",
            "visibility": Visibility.INTERNAL.value,
            "file": _file("plan.pdf"),
        },
    )
    assert response.status_code == 302
    document = PropertyDocument.objects.get()
    assert document.property == record
    assert document.uploaded_by == user
    assert document.organization == organization


@pytest.mark.django_db
def test_visibility_toggle_releases_and_withdraws(client, setup):
    user, organization, _municipality, record = setup
    record.is_public = True
    record.save(update_fields=["is_public"])
    document = _document(organization, record)

    client.force_login(user)
    client.post(reverse("documents:visibility", args=[document.pk]))
    document.refresh_from_db()
    assert document.visibility == Visibility.PUBLIC

    client.post(reverse("documents:visibility", args=[document.pk]))
    document.refresh_from_db()
    assert document.visibility == Visibility.INTERNAL


@pytest.mark.django_db
def test_visibility_toggle_refuses_a_sensitive_kind(client, setup):
    user, organization, _municipality, record = setup
    document = _document(organization, record, kind=DocumentKind.CORRESPONDENCE)
    client.force_login(user)
    client.post(reverse("documents:visibility", args=[document.pk]))
    document.refresh_from_db()
    assert document.visibility == Visibility.INTERNAL


@pytest.mark.django_db
def test_documents_are_isolated_between_municipalities(client, setup, municipal_staff):
    _user, organization, _municipality, record = setup
    _document(organization, record, title="Ours only")
    other, _org, _mun = municipal_staff(username="other_doc")

    client.force_login(other)
    body = client.get(reverse("documents:list")).content.decode()
    assert "Ours only" not in body


@pytest.mark.django_db
def test_external_body_reads_but_cannot_upload(client, setup, make_member):
    _user, organization, _municipality, record = setup
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_d"
    )
    client.force_login(agency)
    assert client.get(reverse("documents:list")).status_code == 200
    assert client.get(reverse("documents:create", args=[record.pk])).status_code == 403


@pytest.mark.django_db
def test_citizens_cannot_see_documents(client, setup, make_user):
    citizen = make_user(username="citizen_d")
    client.force_login(citizen)
    assert client.get(reverse("documents:list")).status_code == 403


# --- Public surface --------------------------------------------------------


@pytest.mark.django_db
def test_only_released_photos_reach_the_public_map(client, setup):
    _user, organization, _municipality, record = setup
    record.is_public = True
    record.location = Point(12.3, 50.6, srid=4326)
    record.save(update_fields=["is_public", "location"])

    _document(organization, record, title="Internal shot")
    payload = client.get(reverse("reports:map_data")).json()
    assert payload["features"][0]["properties"]["photo"] is None

    released = _document(
        organization, record, title="Front view", visibility=Visibility.PUBLIC
    )
    payload = client.get(reverse("reports:map_data")).json()
    assert payload["features"][0]["properties"]["photo"] == released.file.url


@pytest.mark.django_db
def test_a_released_site_plan_is_not_used_as_the_map_photo(client, setup):
    _user, organization, _municipality, record = setup
    record.is_public = True
    record.location = Point(12.3, 50.6, srid=4326)
    record.save(update_fields=["is_public", "location"])
    _document(
        organization,
        record,
        kind=DocumentKind.SITE_PLAN,
        visibility=Visibility.PUBLIC,
        title="Plan",
    )
    payload = client.get(reverse("reports:map_data")).json()
    assert payload["features"][0]["properties"]["photo"] is None
