import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from apps.municipalities.models import District, Module
from apps.municipalities.resolution import (
    map_defaults,
    municipality_for_host,
    municipality_for_point,
)
from organizations.models import Role


def _square(x, y, size=0.1):
    """A small square polygon with its lower-left corner at (x, y)."""
    return Polygon(
        ((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))
    )


# --- Modules ---------------------------------------------------------------


@pytest.mark.django_db
def test_modules_fall_back_to_platform_defaults(make_municipality):
    municipality = make_municipality()
    assert municipality.module_enabled(Module.PUBLIC_MAP) is True
    # Future-phase modules stay off until a municipality asks for them.
    assert municipality.module_enabled(Module.OWNER_PORTAL) is False


@pytest.mark.django_db
def test_module_override_survives_and_is_reversible(make_municipality):
    municipality = make_municipality()
    municipality.set_module(Module.PUBLIC_MAP, False)
    assert municipality.module_enabled(Module.PUBLIC_MAP) is False
    assert Module.PUBLIC_MAP not in municipality.enabled_modules()

    municipality.set_module(Module.PUBLIC_MAP, True)
    assert municipality.module_enabled(Module.PUBLIC_MAP) is True


@pytest.mark.django_db
def test_enabled_modules_merges_defaults_and_overrides(make_municipality):
    municipality = make_municipality()
    municipality.set_module(Module.OWNER_PORTAL, True)
    municipality.set_module(Module.HERITAGE, False)
    enabled = municipality.enabled_modules()
    assert Module.OWNER_PORTAL in enabled
    assert Module.HERITAGE not in enabled
    assert Module.PUBLIC_MAP in enabled


# --- Geography -------------------------------------------------------------


@pytest.mark.django_db
def test_municipality_for_point_uses_the_boundary(make_municipality):
    inside = make_municipality(name="Inside", boundary=MultiPolygon(_square(12.3, 50.6)))
    make_municipality(name="Elsewhere", boundary=MultiPolygon(_square(13.7, 51.0)))

    assert municipality_for_point(Point(12.35, 50.65, srid=4326)) == inside
    assert municipality_for_point(Point(0.0, 0.0, srid=4326)) is None
    assert municipality_for_point(None) is None


@pytest.mark.django_db
def test_municipality_without_boundary_never_matches(make_municipality):
    """Guessing would misroute reports, so no boundary means no attribution."""
    municipality = make_municipality(name="No geodata yet")
    assert municipality.boundary is None
    assert municipality.contains(Point(12.35, 50.65, srid=4326)) is False
    assert municipality_for_point(Point(12.35, 50.65, srid=4326)) is None


@pytest.mark.django_db
def test_district_for_point(make_municipality):
    municipality = make_municipality(boundary=MultiPolygon(_square(12.0, 50.0, size=1.0)))
    centre = District.objects.create(
        municipality=municipality,
        name="Centre",
        boundary=MultiPolygon(_square(12.1, 50.1)),
    )
    District.objects.create(
        municipality=municipality,
        name="North",
        boundary=MultiPolygon(_square(12.5, 50.5)),
    )

    assert municipality.district_for_point(Point(12.15, 50.15, srid=4326)) == centre
    assert municipality.district_for_point(Point(12.9, 50.9, srid=4326)) is None


# --- Request resolution ----------------------------------------------------


@pytest.mark.django_db
def test_municipality_for_host_ignores_the_port(make_municipality):
    municipality = make_municipality(name="Hosted", domain="vacancy.example")
    assert municipality_for_host("vacancy.example:8000") == municipality
    assert municipality_for_host("VACANCY.EXAMPLE") == municipality
    assert municipality_for_host("other.example") is None
    assert municipality_for_host("") is None


@pytest.mark.django_db
def test_request_resolves_the_only_municipality(client, make_municipality):
    """The white-label case: one municipality per installation."""
    municipality = make_municipality(name="Solo")
    response = client.get(reverse("pages:home"))
    assert response.context["municipality"] == municipality
    assert response.context["municipality_name"] == "Solo"


@pytest.mark.django_db
def test_request_resolves_nothing_when_ambiguous(client, make_municipality):
    make_municipality(name="One")
    make_municipality(name="Two")
    response = client.get(reverse("pages:home"))
    assert response.context["municipality"] is None


@pytest.mark.django_db
def test_signed_in_staff_see_their_own_municipality(client, make_member, make_municipality):
    staff, organization = make_member(role=Role.URBAN_PLANNING, username="planner")
    own = make_municipality(organization=organization, name="Own")
    make_municipality(name="Someone else")

    client.force_login(staff)
    response = client.get(reverse("pages:home"))
    assert response.context["municipality"] == own


# --- Branding and white label ---------------------------------------------


@pytest.mark.django_db
def test_branding_appears_in_the_page(client, make_municipality):
    make_municipality(name="Reichenbach", primary_colour="#1d4ed8", font_family="Inter")
    body = client.get(reverse("pages:home")).content.decode()
    assert "Reichenbach" in body
    assert "#1d4ed8" in body
    assert "--bs-body-font-family: Inter" in body


@pytest.mark.django_db
def test_legal_texts_come_from_the_municipality(client, make_municipality):
    make_municipality(name="Legal", imprint="Provided by the town of Legal.")
    body = client.get(reverse("pages:imprint")).content.decode()
    assert "Provided by the town of Legal." in body


@pytest.mark.django_db
def test_map_defaults_prefer_the_municipality(make_municipality, settings):
    settings.MAP_DEFAULT_ZOOM = 14
    municipality = make_municipality(centre=Point(12.3, 50.6, srid=4326), default_zoom=16)
    defaults = map_defaults(municipality)
    assert defaults["latitude"] == pytest.approx(50.6)
    assert defaults["longitude"] == pytest.approx(12.3)
    assert defaults["zoom"] == 16

    # With nothing configured, the instance defaults apply.
    assert map_defaults(None)["zoom"] == 14


# --- Administration views --------------------------------------------------


@pytest.mark.django_db
def test_settings_view_requires_manage_rights(client, make_member, make_municipality):
    manager, organization = make_member(role=Role.OWNER, username="mayor")
    make_municipality(organization=organization, name="Managed")
    planner, _ = make_member(
        role=Role.URBAN_PLANNING, organization=organization, username="planner2"
    )

    client.force_login(planner)
    assert client.get(reverse("municipalities:settings")).status_code == 403

    client.force_login(manager)
    assert client.get(reverse("municipalities:settings")).status_code == 200


@pytest.mark.django_db
def test_manager_can_change_branding_without_code(client, make_member, make_municipality):
    manager, organization = make_member(role=Role.OWNER, username="mayor2")
    municipality = make_municipality(organization=organization, name="Before")

    client.force_login(manager)
    response = client.post(
        reverse("municipalities:settings"),
        {
            "name": "After",
            "state": "SN",
            "primary_colour": "#ff0000",
            "font_family": "Georgia, serif",
            "domain": "after.example",
        },
    )
    assert response.status_code == 302
    municipality.refresh_from_db()
    assert municipality.name == "After"
    assert municipality.primary_colour == "#ff0000"
    assert municipality.domain == "after.example"


@pytest.mark.django_db
def test_module_form_toggles_modules(client, make_member, make_municipality):
    manager, organization = make_member(role=Role.OWNER, username="mayor3")
    municipality = make_municipality(organization=organization)

    client.force_login(manager)
    response = client.post(
        reverse("municipalities:modules"),
        {Module.OWNER_PORTAL.value: "on", Module.PUBLIC_MAP.value: "on"},
    )
    assert response.status_code == 302
    assert municipality.module_enabled(Module.OWNER_PORTAL) is True
    assert municipality.module_enabled(Module.PUBLIC_MAP) is True
    # Unchecked boxes switch their module off explicitly.
    assert municipality.module_enabled(Module.HERITAGE) is False


@pytest.mark.django_db
def test_citizens_cannot_reach_the_administration(client, make_user, make_municipality):
    make_municipality(name="Closed")
    citizen = make_user(username="citizen2")
    client.force_login(citizen)
    assert client.get(reverse("municipalities:settings")).status_code == 403
    assert client.get(reverse("municipalities:districts")).status_code == 403


@pytest.mark.django_db
def test_districts_are_scoped_to_the_own_municipality(
    client, make_member, make_municipality
):
    staff, organization = make_member(role=Role.OWNER, username="owner_a")
    own = make_municipality(organization=organization, name="Own town")
    District.objects.create(municipality=own, name="Own district")

    other = make_municipality(name="Other town")
    District.objects.create(municipality=other, name="Foreign district")

    client.force_login(staff)
    body = client.get(reverse("municipalities:districts")).content.decode()
    assert "Own district" in body
    assert "Foreign district" not in body


@pytest.mark.django_db
def test_district_names_are_unique_per_municipality(make_municipality):
    from django.db import IntegrityError

    municipality = make_municipality()
    District.objects.create(municipality=municipality, name="Centre")
    with pytest.raises(IntegrityError):
        District.objects.create(municipality=municipality, name="Centre")
