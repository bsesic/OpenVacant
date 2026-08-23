import json

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.geodata import geocoding
from apps.geodata.models import GeoFeature, GeoLayer, LayerCategory, SpatialContext
from apps.geodata.services import refresh_context, refresh_context_for_queryset
from apps.properties.models import Property
from organizations.models import Role


def _square(x, y, size=0.1):
    return Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)))


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="gis_staff")
    return user, organization, municipality


@pytest.fixture
def make_layer(setup):
    _user, organization, _municipality = setup

    def _make(category, name=None, geometry=None, **extra):
        layer = GeoLayer.objects.create(
            organization=organization,
            name=name or f"{category} layer",
            slug=extra.pop("slug", f"{category}-layer"),
            category=category,
            **extra,
        )
        GeoFeature.objects.create(
            layer=layer,
            name=f"{category} area",
            geometry=geometry or MultiPolygon(_square(12.3, 50.6)),
        )
        return layer

    return _make


# --- Context resolution ----------------------------------------------------


@pytest.mark.django_db
def test_context_sets_the_flags_of_the_layers_it_falls_inside(setup, make_layer):
    _user, organization, _municipality = setup
    make_layer(LayerCategory.HERITAGE, slug="heritage")
    make_layer(LayerCategory.REDEVELOPMENT, slug="redevelopment")
    make_layer(
        LayerCategory.FUNDING, slug="funding", geometry=MultiPolygon(_square(13.5, 51.5))
    )
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )

    flags = refresh_context(record)
    record.refresh_from_db()
    assert record.is_heritage_protected is True
    assert record.in_redevelopment_area is True
    # The funding layer is elsewhere, so the flag stays false.
    assert record.in_funding_area is False
    assert "is_heritage_protected" in flags
    assert record.context_updated_at is not None


@pytest.mark.django_db
def test_context_rows_explain_why_a_flag_is_set(setup, make_layer):
    _user, organization, _municipality = setup
    layer = make_layer(LayerCategory.HERITAGE, slug="ensemble")
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    refresh_context(record)

    context = SpatialContext.objects.get(property=record)
    assert context.feature.layer == layer
    assert context.category == LayerCategory.HERITAGE


@pytest.mark.django_db
def test_a_record_without_a_location_has_its_flags_cleared(setup, make_layer):
    _user, organization, _municipality = setup
    make_layer(LayerCategory.HERITAGE, slug="heritage2")
    record = Property.objects.create(
        organization=organization, location=None, is_heritage_protected=True
    )
    refresh_context(record)
    record.refresh_from_db()
    # A stale flag is worse than none: nothing can be attributed without a point.
    assert record.is_heritage_protected is False


@pytest.mark.django_db
def test_deactivating_a_layer_removes_its_context(setup, make_layer):
    _user, organization, _municipality = setup
    layer = make_layer(LayerCategory.REDEVELOPMENT, slug="redev2")
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    refresh_context(record)
    record.refresh_from_db()
    assert record.in_redevelopment_area is True

    layer.is_active = False
    layer.save(update_fields=["is_active"])
    refresh_context(record)
    record.refresh_from_db()
    assert record.in_redevelopment_area is False
    assert SpatialContext.objects.filter(property=record).count() == 0


@pytest.mark.django_db
def test_layers_of_another_municipality_are_ignored(setup, make_municipality):
    _user, organization, _municipality = setup
    other = make_municipality(name="Elsewhere")
    foreign = GeoLayer.objects.create(
        organization=other.organization,
        name="Foreign heritage",
        slug="foreign",
        category=LayerCategory.HERITAGE,
    )
    GeoFeature.objects.create(
        layer=foreign, name="Foreign area", geometry=MultiPolygon(_square(12.3, 50.6))
    )
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    refresh_context(record)
    record.refresh_from_db()
    assert record.is_heritage_protected is False


@pytest.mark.django_db
def test_bulk_refresh_reports_how_many_changed(setup, make_layer):
    _user, organization, _municipality = setup
    make_layer(LayerCategory.HERITAGE, slug="bulk")
    inside = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    Property.objects.create(organization=organization, location=Point(0.0, 0.0, srid=4326))

    changed = refresh_context_for_queryset(Property.objects.filter(organization=organization))
    assert changed == 1
    inside.refresh_from_db()
    assert inside.is_heritage_protected is True


# --- Import ----------------------------------------------------------------


def _geojson(tmp_path, features):
    path = tmp_path / "layer.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return str(path)


@pytest.mark.django_db
def test_import_creates_a_layer_and_its_features(setup, tmp_path, capsys):
    _user, _organization, municipality = setup
    municipality.municipality_key = "14523250"
    municipality.save(update_fields=["municipality_key"])

    path = _geojson(
        tmp_path,
        [
            {
                "type": "Feature",
                "properties": {"name": "Old town", "id": "A1"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[12.3, 50.6], [12.4, 50.6], [12.4, 50.7], [12.3, 50.7], [12.3, 50.6]]
                    ],
                },
            }
        ],
    )
    call_command(
        "import_geojson",
        path,
        municipality="14523250",
        name="Redevelopment areas",
        category=LayerCategory.REDEVELOPMENT.value,
        source="State geodata portal",
    )
    layer = GeoLayer.objects.get(slug="redevelopment-areas")
    assert layer.category == LayerCategory.REDEVELOPMENT
    assert layer.feature_count == 1
    assert layer.imported_at is not None
    feature = layer.features.get()
    assert feature.name == "Old town"
    assert feature.external_id == "A1"
    assert feature.attributes["name"] == "Old town"


@pytest.mark.django_db
def test_reimport_replaces_instead_of_duplicating(setup, tmp_path):
    _user, _organization, municipality = setup
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[12.3, 50.6], [12.4, 50.6], [12.4, 50.7], [12.3, 50.7], [12.3, 50.6]]
        ],
    }
    first = _geojson(
        tmp_path, [{"type": "Feature", "properties": {"name": "A"}, "geometry": polygon}]
    )
    call_command("import_geojson", first, municipality=municipality.name, name="Areas")
    second = _geojson(
        tmp_path,
        [
            {"type": "Feature", "properties": {"name": "B"}, "geometry": polygon},
            {"type": "Feature", "properties": {"name": "C"}, "geometry": polygon},
        ],
    )
    call_command("import_geojson", second, municipality=municipality.name, name="Areas")

    layer = GeoLayer.objects.get(slug="areas")
    assert GeoLayer.objects.count() == 1
    # A merge would leave the removed area silently in place.
    assert sorted(layer.features.values_list("name", flat=True)) == ["B", "C"]


@pytest.mark.django_db
def test_import_skips_features_without_geometry(setup, tmp_path):
    _user, _organization, municipality = setup
    path = _geojson(
        tmp_path,
        [
            {"type": "Feature", "properties": {"name": "No shape"}, "geometry": None},
            {
                "type": "Feature",
                "properties": {"name": "Fine"},
                "geometry": {"type": "Point", "coordinates": [12.3, 50.6]},
            },
        ],
    )
    call_command("import_geojson", path, municipality=municipality.name, name="Mixed")
    assert GeoLayer.objects.get(slug="mixed").feature_count == 1


@pytest.mark.django_db
def test_import_refuses_an_unknown_municipality(tmp_path):
    path = _geojson(tmp_path, [])
    with pytest.raises(CommandError):
        call_command("import_geojson", path, municipality="Nowhere", name="X")


@pytest.mark.django_db
def test_import_can_refresh_the_context_immediately(setup, tmp_path):
    _user, organization, municipality = setup
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    path = _geojson(
        tmp_path,
        [
            {
                "type": "Feature",
                "properties": {"name": "Zone"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[12.3, 50.6], [12.4, 50.6], [12.4, 50.7], [12.3, 50.7], [12.3, 50.6]]
                    ],
                },
            }
        ],
    )
    call_command(
        "import_geojson",
        path,
        municipality=municipality.name,
        name="Funding areas",
        category=LayerCategory.FUNDING.value,
        refresh_context=True,
    )
    record.refresh_from_db()
    assert record.in_funding_area is True


@pytest.mark.django_db
def test_refresh_command_can_target_one_municipality(setup, make_layer, make_municipality):
    _user, organization, municipality = setup
    make_layer(LayerCategory.HERITAGE, slug="target")
    record = Property.objects.create(
        organization=organization, location=Point(12.35, 50.65, srid=4326)
    )
    call_command("refresh_geo_context", municipality=municipality.name)
    record.refresh_from_db()
    assert record.is_heritage_protected is True


# --- Geocoding -------------------------------------------------------------


def test_provider_none_gives_a_geocoder_that_answers_nothing(settings):
    settings.GEOCODER_PROVIDER = "none"
    geocoder = geocoding.get_geocoder()
    assert geocoder.search("Bahnhofstraße") == []
    assert geocoder.reverse(Point(12.3, 50.6, srid=4326)) is None


@pytest.mark.django_db
def test_search_biases_towards_the_municipality(setup, monkeypatch, settings):
    """Without the town name, a street name finds the wrong place entirely."""
    settings.GEOCODER_PROVIDER = "nominatim"
    _user, _organization, municipality = setup
    captured = {}

    def fake_request(self, path, params):
        captured["path"] = path
        captured["params"] = params
        return [
            {
                "display_name": "Bahnhofstraße 12, Reichenbach",
                "lat": "50.6236",
                "lon": "12.3036",
                "address": {
                    "road": "Bahnhofstraße",
                    "house_number": "12",
                    "postcode": "08468",
                    "town": "Reichenbach im Vogtland",
                },
            }
        ]

    monkeypatch.setattr(geocoding.NominatimGeocoder, "_request", fake_request)
    results = geocoding.NominatimGeocoder().search("Bahnhofstraße 12", municipality=municipality)

    assert municipality.name in captured["params"]["q"]
    assert captured["params"]["countrycodes"] == "de"
    assert results[0]["street"] == "Bahnhofstraße"
    assert results[0]["postal_code"] == "08468"
    assert results[0]["city"] == "Reichenbach im Vogtland"


@pytest.mark.django_db
def test_address_search_endpoint_returns_results(client, setup, monkeypatch, settings):
    settings.GEOCODER_PROVIDER = "nominatim"
    monkeypatch.setattr(
        geocoding.NominatimGeocoder,
        "search",
        lambda self, query, municipality=None, limit=5: [
            {
                "label": "Bahnhofstraße 12",
                "latitude": 50.6,
                "longitude": 12.3,
                "street": "Bahnhofstraße",
                "house_number": "12",
                "postal_code": "08468",
                "city": "Reichenbach",
            }
        ],
    )
    payload = client.get(reverse("geodata:address_search"), {"q": "Bahnhof"}).json()
    assert payload["results"][0]["street"] == "Bahnhofstraße"


@pytest.mark.django_db
def test_address_search_ignores_very_short_queries(client, setup):
    payload = client.get(reverse("geodata:address_search"), {"q": "ab"}).json()
    assert payload["results"] == []


@pytest.mark.django_db
def test_address_search_survives_an_unavailable_provider(client, setup, monkeypatch, settings):
    settings.GEOCODER_PROVIDER = "nominatim"

    def boom(self, query, municipality=None, limit=5):
        raise geocoding.GeocodingUnavailable("timeout")

    monkeypatch.setattr(geocoding.NominatimGeocoder, "search", boom)
    response = client.get(reverse("geodata:address_search"), {"q": "Bahnhofstraße"})
    # The form must stay usable when the upstream service is down.
    assert response.status_code == 503
    assert response.json()["results"] == []


# --- Views -----------------------------------------------------------------


@pytest.mark.django_db
def test_layer_list_is_internal_and_scoped(client, setup, make_layer, make_user):
    user, _organization, _municipality = setup
    make_layer(LayerCategory.HERITAGE, name="Our heritage", slug="ours")

    citizen = make_user(username="citizen_g")
    client.force_login(citizen)
    assert client.get(reverse("geodata:layers")).status_code == 403

    client.force_login(user)
    body = client.get(reverse("geodata:layers")).content.decode()
    assert "Our heritage" in body


@pytest.mark.django_db
def test_external_body_may_read_the_layer_list(client, setup, make_member):
    _user, organization, _municipality = setup
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_g"
    )
    client.force_login(agency)
    assert client.get(reverse("geodata:layers")).status_code == 200
