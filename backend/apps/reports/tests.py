import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.municipalities.models import District, Module
from apps.properties.choices import (
    AssessmentSource,
    DamageType,
    RecordStatus,
    VacancyStatus,
)
from apps.properties.models import Property
from apps.reports.models import Report, ReportCategory, ReportStatus
from apps.reports.services import create_property_from_report
from organizations.models import Role


@pytest.fixture
def _media(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


def _square(x, y, size=1.0):
    return Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)))


@pytest.fixture
def instance(make_municipality):
    """A single-municipality installation, which is the white-label default."""
    return make_municipality(name="Reichenbach", municipality_key="14523250")


def _valid_payload(**overrides):
    payload = {
        "category": ReportCategory.SUSPECTED_VACANCY.value,
        "description": "Windows boarded up for over a year.",
        "street": "Bahnhofstraße",
        "house_number": "12",
        "postal_code": "08468",
        "city": "Reichenbach im Vogtland",
        "latitude": "50.6236",
        "longitude": "12.3036",
        "accepted_privacy_policy": "on",
        "accepted_terms": "on",
    }
    payload.update(overrides)
    return payload


# --- Submitting ------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_visitor_can_submit_a_report(client, instance):
    response = client.post(reverse("reports:create"), _valid_payload())
    assert response.status_code == 302

    report = Report.objects.get()
    assert report.organization == instance.organization
    assert report.is_anonymous
    assert report.status == ReportStatus.SUBMITTED
    assert report.location is not None
    assert report.consent_given_at is not None
    assert report.reference.startswith("M-")
    assert response.url == reverse("reports:submitted", kwargs={"reference": report.reference})


@pytest.mark.django_db
def test_consent_is_required(client, instance):
    payload = _valid_payload()
    del payload["accepted_privacy_policy"]
    response = client.post(reverse("reports:create"), payload)
    assert response.status_code == 200
    assert Report.objects.count() == 0
    assert "accepted_privacy_policy" in response.context["form"].errors


@pytest.mark.django_db
def test_a_report_needs_a_location_or_an_address(client, instance):
    payload = _valid_payload(latitude="", longitude="", street="", city="", postal_code="")
    response = client.post(reverse("reports:create"), payload)
    assert response.status_code == 200
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_an_address_alone_is_enough(client, instance):
    """The map is an aid, not the only way in."""
    response = client.post(
        reverse("reports:create"), _valid_payload(latitude="", longitude="")
    )
    assert response.status_code == 302
    report = Report.objects.get()
    assert report.location is None
    assert report.street == "Bahnhofstraße"


@pytest.mark.django_db
def test_the_honeypot_field_rejects_bots(client, instance):
    response = client.post(
        reverse("reports:create"), _valid_payload(website="http://spam.example")
    )
    assert response.status_code == 200
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_reports_are_rate_limited_per_address(client, instance, settings):
    settings.REPORT_RATE_LIMIT = "2/h"
    # The decorator reads the rate at import time, so drive the limiter directly
    # to prove the configured limit is what blocks a flood.
    from django_ratelimit.core import is_ratelimited

    class _Request:
        META = {"REMOTE_ADDR": "203.0.113.5"}
        method = "POST"
        POST = {}
        GET = {}
        LANGUAGE_CODE = "de"

    limited = [
        is_ratelimited(
            request=_Request(),
            group="reports.flood",
            key="ip",
            rate="2/h",
            method="POST",
            increment=True,
        )
        for _ in range(3)
    ]
    assert limited == [False, False, True]


@pytest.mark.django_db
def test_signed_in_reporter_is_recorded_and_not_asked_for_contact(client, instance, make_user):
    citizen = make_user(username="reporter")
    client.force_login(citizen)

    form_fields = client.get(reverse("reports:create")).context["form"].fields
    assert "contact_email" not in form_fields

    client.post(reverse("reports:create"), _valid_payload())
    report = Report.objects.get()
    assert report.submitted_by == citizen
    assert not report.is_anonymous


@pytest.mark.django_db
def test_anonymous_reporting_can_be_switched_off(client, instance):
    instance.set_module(Module.ANONYMOUS_REPORTS, False)
    response = client.get(reverse("reports:create"))
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_photos_are_stored_and_default_to_internal(client, instance, _media):
    image = SimpleUploadedFile(
        "front.jpg",
        b"\xff\xd8\xff\xdb" + b"0" * 64,
        content_type="image/jpeg",
    )
    payload = _valid_payload()
    payload["photos"] = image
    response = client.post(reverse("reports:create"), payload)
    assert response.status_code == 302
    photo = Report.objects.get().photos.get()
    # Street photography can show people and number plates.
    assert photo.is_public is False


@pytest.mark.django_db
def test_too_many_photos_are_refused(client, instance, settings, _media):
    settings.REPORT_MAX_PHOTOS = 2
    images = [
        SimpleUploadedFile(f"p{i}.jpg", b"\xff\xd8\xff\xdb" + b"0" * 32, "image/jpeg")
        for i in range(3)
    ]
    payload = _valid_payload()
    payload["photos"] = images
    response = client.post(reverse("reports:create"), payload)
    assert response.status_code == 200
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_marked_damage_is_kept_as_an_observation(client, instance):
    payload = _valid_payload()
    payload["damage"] = [DamageType.ROOF.value, DamageType.WINDOWS.value]
    client.post(reverse("reports:create"), payload)
    report = Report.objects.get()
    assert set(report.damage_types) == {DamageType.ROOF.value, DamageType.WINDOWS.value}
    assert len(report.damage_labels) == 2


@pytest.mark.django_db
def test_district_is_derived_from_the_marker(client, instance):
    instance.boundary = MultiPolygon(_square(12.0, 50.0))
    instance.save(update_fields=["boundary"])
    centre = District.objects.create(
        municipality=instance, name="Centre", boundary=MultiPolygon(_square(12.3, 50.6, 0.2))
    )
    client.post(reverse("reports:create"), _valid_payload())
    assert Report.objects.get().district == centre


@pytest.mark.django_db
def test_feedback_needs_a_way_to_reply(client, instance):
    payload = _valid_payload(wants_feedback="on")
    response = client.post(reverse("reports:create"), payload)
    assert response.status_code == 200
    assert "wants_feedback" in response.context["form"].errors


# --- Own reports -----------------------------------------------------------


@pytest.mark.django_db
def test_reporters_see_only_their_own_reports(client, instance, make_user):
    first = make_user(username="first")
    second = make_user(username="second")
    Report.objects.create(
        organization=instance.organization, submitted_by=first, description="Mine", city="Town"
    )
    Report.objects.create(
        organization=instance.organization, submitted_by=second, description="Theirs", city="Town"
    )

    client.force_login(first)
    body = client.get(reverse("reports:mine")).content.decode()
    assert "Mine" in body
    assert "Theirs" not in body


@pytest.mark.django_db
def test_own_reports_require_signing_in(client, instance):
    response = client.get(reverse("reports:mine"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_anonymous_reports_do_not_appear_in_the_data_export(client, instance, make_user):
    """Submitting anonymously means the report cannot be tied back to a person."""
    citizen = make_user(username="exporter")
    Report.objects.create(
        organization=instance.organization, submitted_by=citizen, city="Town", description="Mine"
    )
    Report.objects.create(organization=instance.organization, city="Town", description="Anon")

    client.force_login(citizen)
    payload = client.get(reverse("compliance:data_export")).json()
    descriptions = [entry["description"] for entry in payload["reports"]]
    assert descriptions == ["Mine"]


# --- Public map ------------------------------------------------------------


@pytest.mark.django_db
def test_public_map_shows_only_released_records_and_public_fields(client, instance):
    published = Property.objects.create(
        organization=instance.organization,
        street="Marktplatz",
        location=Point(12.3, 50.6, srid=4326),
        public_description="Vacant shop",
        internal_description="Owner in dispute with the heirs",
        is_public=True,
    )
    Property.objects.create(
        organization=instance.organization,
        street="Nebenstraße",
        location=Point(12.31, 50.61, srid=4326),
        internal_description="Not released",
        is_public=False,
    )

    payload = client.get(reverse("reports:map_data")).json()
    references = [f["properties"]["reference"] for f in payload["features"]]
    assert references == [published.reference]

    body = client.get(reverse("reports:map_data")).content.decode()
    assert "Vacant shop" in body
    assert "heirs" not in body
    assert "Not released" not in body


@pytest.mark.django_db
def test_records_without_a_location_are_left_off_the_map(client, instance):
    Property.objects.create(
        organization=instance.organization, city="Town", is_public=True, location=None
    )
    payload = client.get(reverse("reports:map_data")).json()
    assert payload["features"] == []


@pytest.mark.django_db
def test_the_public_map_can_be_switched_off(client, instance):
    instance.set_module(Module.PUBLIC_MAP, False)
    assert client.get(reverse("reports:map")).status_code == 403
    assert client.get(reverse("reports:map_data")).status_code == 403


# --- Moderation ------------------------------------------------------------


@pytest.mark.django_db
def test_citizens_cannot_reach_the_moderation_queue(client, instance, make_user):
    citizen = make_user(username="nosy")
    client.force_login(citizen)
    assert client.get(reverse("reports:list")).status_code == 403


@pytest.mark.django_db
def test_reports_are_isolated_between_municipalities(client, instance, municipal_staff):
    other_staff, _other_org, _other_mun = municipal_staff(username="other_staff")
    report = Report.objects.create(
        organization=instance.organization, city="Town", description="Only for Reichenbach"
    )
    client.force_login(other_staff)
    assert client.get(reverse("reports:detail", args=[report.pk])).status_code == 404


@pytest.mark.django_db
def test_moderation_decision_is_recorded(client, instance, make_member):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY,
        organization=instance.organization,
        username="moderator",
    )
    report = Report.objects.create(organization=instance.organization, city="Town")

    client.force_login(staff)
    response = client.post(
        reverse("reports:moderate", args=[report.pk]),
        {"status": ReportStatus.REJECTED.value, "moderation_note": "Building is occupied"},
    )
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.status == ReportStatus.REJECTED
    assert report.moderated_by == staff
    assert report.moderated_at is not None
    assert report.moderation_note == "Building is occupied"


@pytest.mark.django_db
def test_external_body_cannot_moderate(client, instance, make_member):
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=instance.organization, username="landkreis_r"
    )
    report = Report.objects.create(organization=instance.organization, city="Town")
    client.force_login(agency)
    assert client.get(reverse("reports:detail", args=[report.pk])).status_code == 200
    assert client.post(
        reverse("reports:accept", args=[report.pk])
    ).status_code == 403


# --- Turning reports into records -----------------------------------------


@pytest.mark.django_db
def test_accepting_a_report_creates_a_record_in_the_preliminary_check(
    client, instance, make_member
):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="accepter"
    )
    report = Report.objects.create(
        organization=instance.organization,
        street="Zwickauer Straße",
        house_number="7",
        city="Reichenbach im Vogtland",
        location=Point(12.3036, 50.6236, srid=4326),
        description="Empty for years, letterbox overflowing",
        damage_types=[DamageType.ROOF.value],
    )

    client.force_login(staff)
    response = client.post(reverse("reports:accept", args=[report.pk]))
    assert response.status_code == 302

    record = Property.objects.get()
    report.refresh_from_db()
    assert report.property == record
    assert report.status == ReportStatus.ACCEPTED
    assert report.moderated_by == staff

    # A report is a suspicion: the record starts its verification, it is not
    # confirmed, and the occupancy is only "suspected".
    assert record.status == RecordStatus.PRE_CHECK
    assert record.vacancy_status == VacancyStatus.SUSPECTED_VACANT
    assert not record.is_confirmed
    assert record.condition_source == AssessmentSource.CITIZEN_OBSERVATION
    assert record.damages.get().source == AssessmentSource.CITIZEN_OBSERVATION
    assert record.status_transitions.count() == 1


@pytest.mark.django_db
def test_reporter_text_never_lands_in_the_public_description(instance):
    report = Report.objects.create(
        organization=instance.organization,
        city="Town",
        description="Belongs to the Müller family, nobody has lived there since Anna died",
    )
    record = create_property_from_report(report)
    # Free text from the public can name residents and owners, so it stays
    # internal until somebody reviews it.
    assert record.public_description == ""
    assert "Müller" in record.internal_description
    assert record.is_public is False
    assert report.reference in record.sources


@pytest.mark.django_db
def test_a_report_can_be_attached_to_a_known_record(client, instance, make_member):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="attacher"
    )
    existing = Property.objects.create(organization=instance.organization, street="Altmarkt")
    report = Report.objects.create(organization=instance.organization, street="Altmarkt")

    client.force_login(staff)
    response = client.post(
        reverse("reports:attach", args=[report.pk]), {"property": existing.pk}
    )
    assert response.status_code == 302
    report.refresh_from_db()
    existing.refresh_from_db()
    assert report.property == existing
    assert report.status == ReportStatus.ACCEPTED
    assert report.reference in existing.sources
    # Attaching must not create a second record for the same building.
    assert Property.objects.count() == 1


@pytest.mark.django_db
def test_accepting_twice_does_not_create_a_second_record(client, instance, make_member):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="twice"
    )
    report = Report.objects.create(organization=instance.organization, city="Town")
    client.force_login(staff)
    client.post(reverse("reports:accept", args=[report.pk]))
    client.post(reverse("reports:accept", args=[report.pk]))
    assert Property.objects.count() == 1


@pytest.mark.django_db
def test_a_photo_can_be_released_deliberately(client, instance, make_member, _media):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="releaser"
    )
    report = Report.objects.create(organization=instance.organization, city="Town")
    photo = report.photos.create(
        image=SimpleUploadedFile("a.jpg", b"\xff\xd8\xff\xdb" + b"0" * 16, "image/jpeg")
    )
    assert photo.is_public is False

    client.force_login(staff)
    client.post(reverse("reports:photo_publication", args=[report.pk, photo.pk]))
    photo.refresh_from_db()
    assert photo.is_public is True

    client.post(reverse("reports:photo_publication", args=[report.pk, photo.pk]))
    photo.refresh_from_db()
    assert photo.is_public is False


@pytest.mark.django_db
def test_report_references_are_sequential_per_tenant(instance, make_municipality):
    other = make_municipality(name="Elsewhere")
    a1 = Report.objects.create(organization=instance.organization, city="A")
    a2 = Report.objects.create(organization=instance.organization, city="A")
    b1 = Report.objects.create(organization=other.organization, city="B")
    assert a1.reference.endswith("0001")
    assert a2.reference.endswith("0002")
    assert b1.reference.endswith("0001")


# --- Authorised photo delivery --------------------------------------------


@pytest.mark.django_db
def test_an_unreleased_photo_is_refused_to_the_public(client, instance, _media):
    report = Report.objects.create(organization=instance.organization, city="Town")
    photo = report.photos.create(
        image=SimpleUploadedFile("x.jpg", b"\xff\xd8\xff\xdb" + b"0" * 16, "image/jpeg")
    )
    url = reverse("reports:photo_download", args=[report.pk, photo.pk])
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_a_released_photo_is_available_to_anyone(client, instance, _media):
    report = Report.objects.create(organization=instance.organization, city="Town")
    photo = report.photos.create(
        image=SimpleUploadedFile("y.jpg", b"\xff\xd8\xff\xdb" + b"0" * 16, "image/jpeg"),
        is_public=True,
    )
    url = reverse("reports:photo_download", args=[report.pk, photo.pk])
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_staff_may_see_an_unreleased_photo(client, instance, make_member, _media):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="photo_staff"
    )
    report = Report.objects.create(organization=instance.organization, city="Town")
    photo = report.photos.create(
        image=SimpleUploadedFile("z.jpg", b"\xff\xd8\xff\xdb" + b"0" * 16, "image/jpeg")
    )
    client.force_login(staff)
    url = reverse("reports:photo_download", args=[report.pk, photo.pk])
    assert client.get(url).status_code == 200
