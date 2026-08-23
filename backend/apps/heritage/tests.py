import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from apps.geodata.models import GeoFeature, GeoLayer, LayerCategory
from apps.geodata.services import refresh_context
from apps.heritage.models import CheckResult, HeritageCheck, MonumentRecord, ProtectionScope
from apps.municipalities.models import Module
from apps.properties.choices import VacancyStatus
from apps.properties.models import Property
from organizations.models import Role


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="heritage_staff")
    record = Property.objects.create(
        organization=organization, street="Kirchplatz", city="Reichenbach"
    )
    return user, organization, municipality, record


# --- Checks ----------------------------------------------------------------


@pytest.mark.django_db
def test_a_conclusive_check_sets_the_flag(client, setup):
    user, _organization, _municipality, record = setup
    assert record.is_heritage_protected is False

    client.force_login(user)
    response = client.post(
        reverse("heritage:check_create", args=[record.pk]),
        {
            "result": CheckResult.PROTECTED.value,
            "checked_on": "2026-08-12",
            "authority_reference": "LfD/2026/114",
        },
    )
    assert response.status_code == 302
    record.refresh_from_db()
    assert record.is_heritage_protected is True

    check = HeritageCheck.objects.get()
    assert check.checked_by == user
    assert check.is_conclusive is True
    assert check.authority_reference == "LfD/2026/114"


@pytest.mark.django_db
def test_an_unclear_check_is_kept_but_settles_nothing(client, setup):
    user, _organization, _municipality, record = setup
    client.force_login(user)
    client.post(
        reverse("heritage:check_create", args=[record.pk]),
        {"result": CheckResult.UNCLEAR.value, "checked_on": "2026-08-12"},
    )
    record.refresh_from_db()
    check = HeritageCheck.objects.get()
    # "We do not know" must not be recorded as "not listed".
    assert check.is_conclusive is False
    assert record.is_heritage_protected is False


@pytest.mark.django_db
def test_a_check_outranks_the_geodata_layer(setup):
    _user, organization, _municipality, record = setup
    layer = GeoLayer.objects.create(
        organization=organization,
        name="Heritage areas",
        slug="heritage-areas",
        category=LayerCategory.HERITAGE,
    )
    GeoFeature.objects.create(
        layer=layer,
        name="Old town",
        geometry=MultiPolygon(
            Polygon(((12.3, 50.6), (12.4, 50.6), (12.4, 50.7), (12.3, 50.7), (12.3, 50.6)))
        ),
    )
    record.location = Point(12.35, 50.65, srid=4326)
    record.save(update_fields=["location"])
    refresh_context(record)
    record.refresh_from_db()
    assert record.is_heritage_protected is True

    # The authority answered that it is not listed after all.
    check = HeritageCheck.objects.create(
        organization=organization, property=record, result=CheckResult.NOT_PROTECTED
    )
    assert check.apply_to_property() is True
    record.refresh_from_db()
    assert record.is_heritage_protected is False


@pytest.mark.django_db
def test_applying_the_same_result_twice_changes_nothing(setup):
    _user, organization, _municipality, record = setup
    check = HeritageCheck.objects.create(
        organization=organization, property=record, result=CheckResult.PROTECTED
    )
    assert check.apply_to_property() is True
    assert check.apply_to_property() is False


# --- Monuments -------------------------------------------------------------


@pytest.mark.django_db
def test_monuments_are_listed_with_the_vacant_count(client, setup):
    user, organization, _municipality, record = setup
    MonumentRecord.objects.create(
        organization=organization,
        property=record,
        designation="Weberhaus",
        monument_id="09301234",
        scope=ProtectionScope.SINGLE,
        authority="Lower heritage authority",
    )
    record.is_heritage_protected = True
    record.save(update_fields=["is_heritage_protected"])
    record.set_vacancy_status(VacancyStatus.VACANT)

    client.force_login(user)
    response = client.get(reverse("heritage:monuments"))
    assert response.status_code == 200
    assert b"Weberhaus" in response.content
    assert response.context["vacant_monuments"] == 1


@pytest.mark.django_db
def test_monuments_are_isolated_between_municipalities(client, setup, municipal_staff):
    _user, organization, _municipality, _record = setup
    MonumentRecord.objects.create(organization=organization, designation="Ours only")
    other, _org, _mun = municipal_staff(username="other_heritage")

    client.force_login(other)
    body = client.get(reverse("heritage:monuments")).content.decode()
    assert "Ours only" not in body


@pytest.mark.django_db
def test_the_heritage_module_can_be_switched_off(client, setup):
    user, _organization, municipality, record = setup
    municipality.set_module(Module.HERITAGE, False)
    client.force_login(user)
    assert client.get(reverse("heritage:monuments")).status_code == 403
    assert client.get(reverse("heritage:check_create", args=[record.pk])).status_code == 403


@pytest.mark.django_db
def test_external_body_can_read_but_not_check(client, setup, make_member):
    _user, organization, _municipality, record = setup
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_h"
    )
    client.force_login(agency)
    assert client.get(reverse("heritage:monuments")).status_code == 200
    assert client.get(reverse("heritage:check_create", args=[record.pk])).status_code == 403


@pytest.mark.django_db
def test_citizens_cannot_see_monuments(client, setup, make_user):
    citizen = make_user(username="citizen_h")
    client.force_login(citizen)
    assert client.get(reverse("heritage:monuments")).status_code == 403
