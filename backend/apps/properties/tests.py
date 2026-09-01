import pytest
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.municipalities.models import District
from apps.parcels.models import Parcel
from apps.properties.choices import (
    AssessmentSource,
    ConditionGrade,
    DamageType,
    Priority,
    PropertyType,
    RecordStatus,
    VacancyStatus,
)
from apps.properties.models import Property, TransitionNotAllowed
from apps.properties.search import search_properties
from apps.vacancies.models import VacancyPeriod, vacancy_duration_days
from organizations.models import Role


@pytest.fixture
def record(municipal_staff):
    """A staff user with a municipality and one plain record."""
    user, organization, municipality = municipal_staff(username="bauamt")
    obj = Property.objects.create(
        organization=organization,
        street="Bahnhofstraße",
        house_number="12",
        postal_code="08468",
        city="Reichenbach im Vogtland",
        location=Point(12.3036, 50.6236, srid=4326),
        created_by=user,
    )
    return user, organization, municipality, obj


# --- Reference numbers -----------------------------------------------------


@pytest.mark.django_db
def test_reference_is_assigned_per_municipality(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="ref1")
    first = Property.objects.create(organization=organization, city="Town")
    second = Property.objects.create(organization=organization, city="Town")
    year = first.recorded_on.year
    assert first.reference == f"MUN-{year}-0001"
    assert second.reference == f"MUN-{year}-0002"


@pytest.mark.django_db
def test_reference_prefix_uses_the_municipality_key(make_municipality, make_tenant):
    organization = make_tenant(name="Reichenbach")
    make_municipality(organization=organization, name="Reichenbach", municipality_key="14523250")
    record = Property.objects.create(organization=organization)
    assert record.reference.startswith("145-")


@pytest.mark.django_db
def test_reference_sequences_are_independent_per_tenant(municipal_staff):
    _u1, org_a, _m1 = municipal_staff(username="a1")
    _u2, org_b, _m2 = municipal_staff(username="b1")
    a = Property.objects.create(organization=org_a)
    b = Property.objects.create(organization=org_b)
    assert a.reference.endswith("0001")
    assert b.reference.endswith("0001")


# --- Address presentation --------------------------------------------------


@pytest.mark.django_db
def test_address_line_falls_back_through_note_and_coordinates(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="addr")
    with_address = Property.objects.create(
        organization=organization, street="Hauptstraße", house_number="1", city="Town"
    )
    assert with_address.address_line == "Hauptstraße 1, Town"

    with_note = Property.objects.create(
        organization=organization, address_note="behind number 14"
    )
    assert with_note.address_line == "behind number 14"

    with_point = Property.objects.create(
        organization=organization, location=Point(12.3, 50.6, srid=4326)
    )
    assert "50.6" in with_point.address_line

    unknown = Property.objects.create(organization=organization)
    assert str(unknown.address_line)


# --- Workflow --------------------------------------------------------------


@pytest.mark.django_db
def test_a_new_record_cannot_jump_straight_to_confirmed(record):
    user, _organization, _municipality, obj = record
    assert obj.status == RecordStatus.NEW
    with pytest.raises(TransitionNotAllowed):
        obj.transition_to(RecordStatus.CONFIRMED, actor=user)
    obj.refresh_from_db()
    assert obj.status == RecordStatus.NEW


@pytest.mark.django_db
def test_the_full_verification_path_is_allowed_and_logged(record):
    user, _organization, _municipality, obj = record
    obj.transition_to(RecordStatus.PRE_CHECK, actor=user, reason="Report plausible")
    obj.transition_to(RecordStatus.ON_SITE_CHECK, actor=user)
    obj.transition_to(RecordStatus.CONFIRMED, actor=user, reason="Vacant on site visit")

    obj.refresh_from_db()
    assert obj.status == RecordStatus.CONFIRMED
    assert obj.is_confirmed

    transitions = list(obj.status_transitions.order_by("created_at"))
    assert [t.to_status for t in transitions] == [
        RecordStatus.PRE_CHECK,
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.CONFIRMED,
    ]
    assert transitions[0].actor == user
    assert transitions[0].reason == "Report plausible"


@pytest.mark.django_db
def test_transition_records_the_check_date(record):
    user, _organization, _municipality, obj = record
    assert obj.last_checked_on is None
    obj.transition_to(RecordStatus.PRE_CHECK, actor=user)
    obj.refresh_from_db()
    assert obj.last_checked_on is not None


@pytest.mark.django_db
def test_transition_to_the_same_status_is_a_no_op(record):
    user, _organization, _municipality, obj = record
    assert obj.transition_to(RecordStatus.NEW, actor=user) is None
    assert obj.status_transitions.count() == 0


@pytest.mark.django_db
def test_archived_records_can_only_be_reopened_into_monitoring(record):
    user, _organization, _municipality, obj = record
    obj.transition_to(RecordStatus.ARCHIVED, actor=user)
    assert obj.allowed_transitions() == [RecordStatus.MONITORING]
    with pytest.raises(TransitionNotAllowed):
        obj.transition_to(RecordStatus.CONFIRMED, actor=user)
    obj.transition_to(RecordStatus.MONITORING, actor=user)
    obj.refresh_from_db()
    assert obj.status == RecordStatus.MONITORING


# --- Vacancy history -------------------------------------------------------


@pytest.mark.django_db
def test_occupancy_change_opens_and_closes_periods(record):
    user, _organization, _municipality, obj = record
    obj.set_vacancy_status(VacancyStatus.VACANT, actor=user, source="Site visit")
    obj.refresh_from_db()
    assert obj.vacancy_status == VacancyStatus.VACANT
    assert obj.is_vacant

    open_periods = obj.vacancy_periods.filter(ended_on__isnull=True)
    assert open_periods.count() == 1
    assert open_periods.first().status == VacancyStatus.VACANT

    obj.set_vacancy_status(VacancyStatus.IN_USE, actor=user)
    assert obj.vacancy_periods.count() == 2
    assert obj.vacancy_periods.filter(ended_on__isnull=True).count() == 1
    closed = obj.vacancy_periods.filter(status=VacancyStatus.VACANT).first()
    assert closed.ended_on is not None
    assert not obj.vacancy_periods.filter(ended_on__isnull=True).first().counts_as_vacancy


@pytest.mark.django_db
def test_periods_are_scoped_to_the_same_tenant(record):
    user, organization, _municipality, obj = record
    obj.set_vacancy_status(VacancyStatus.VACANT, actor=user)
    assert VacancyPeriod.objects.get(property=obj).organization == organization


@pytest.mark.django_db
def test_vacancy_duration_only_counts_actual_vacancy(record):
    user, _organization, _municipality, obj = record
    assert vacancy_duration_days(obj) is None

    obj.set_vacancy_status(VacancyStatus.SUSPECTED_VACANT, actor=user)
    # A suspicion is not vacancy, so it has no measurable duration.
    assert vacancy_duration_days(obj) is None

    obj.set_vacancy_status(VacancyStatus.VACANT, actor=user)
    assert vacancy_duration_days(obj) == 0


@pytest.mark.django_db
def test_repeating_the_same_occupancy_does_not_split_the_period(record):
    user, _organization, _municipality, obj = record
    obj.set_vacancy_status(VacancyStatus.VACANT, actor=user)
    assert obj.set_vacancy_status(VacancyStatus.VACANT, actor=user) is None
    assert obj.vacancy_periods.count() == 1


# --- Damages ---------------------------------------------------------------


@pytest.mark.django_db
def test_damages_are_unique_per_type_and_updatable(record):
    _user, _organization, _municipality, obj = record
    obj.mark_damage(DamageType.ROOF, source=AssessmentSource.CITIZEN_OBSERVATION)
    obj.mark_damage(DamageType.FACADE)
    assert obj.damages.count() == 2

    obj.mark_damage(
        DamageType.ROOF,
        severity="hazardous",
        source=AssessmentSource.STAFF_ASSESSMENT,
        note="Tiles missing",
    )
    assert obj.damages.count() == 2
    roof = obj.damages.get(damage_type=DamageType.ROOF)
    assert roof.severity == "hazardous"
    assert roof.source == AssessmentSource.STAFF_ASSESSMENT


@pytest.mark.django_db
def test_citizen_observation_is_not_an_expert_assessment(record):
    _user, _organization, _municipality, obj = record
    obj.condition = ConditionGrade.COLLAPSE_RISK
    obj.condition_source = AssessmentSource.CITIZEN_OBSERVATION
    obj.save()
    assert obj.is_critical
    assert not obj.is_expert_assessed

    obj.condition_source = AssessmentSource.EXPERT_REPORT
    obj.save()
    assert obj.is_expert_assessed


# --- Validation ------------------------------------------------------------


@pytest.mark.django_db
def test_district_of_another_municipality_is_rejected(municipal_staff, make_municipality):
    _user, organization, _municipality = municipal_staff(username="val1")
    other = make_municipality(name="Elsewhere")
    foreign = District.objects.create(municipality=other, name="Foreign")

    record = Property(organization=organization, district=foreign)
    with pytest.raises(ValidationError) as error:
        record.full_clean()
    assert "district" in error.value.message_dict


@pytest.mark.django_db
def test_more_vacant_units_than_total_is_rejected(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="val2")
    record = Property(organization=organization, units_total=4, units_vacant=5)
    with pytest.raises(ValidationError) as error:
        record.full_clean()
    assert "units_vacant" in error.value.message_dict


# --- Querysets -------------------------------------------------------------


@pytest.mark.django_db
def test_reporting_querysets_encode_the_definitions(municipal_staff):
    user, organization, _municipality = municipal_staff(username="qs")
    suspected = Property.objects.create(
        organization=organization, vacancy_status=VacancyStatus.SUSPECTED_VACANT
    )
    vacant = Property.objects.create(organization=organization)
    vacant.set_vacancy_status(VacancyStatus.VACANT, actor=user)
    vacant.transition_to(RecordStatus.PRE_CHECK, actor=user)
    vacant.transition_to(RecordStatus.ON_SITE_CHECK, actor=user)
    vacant.transition_to(RecordStatus.CONFIRMED, actor=user)
    critical = Property.objects.create(
        organization=organization, condition=ConditionGrade.COLLAPSE_RISK
    )
    published = Property.objects.create(organization=organization, is_public=True)

    scoped = Property.objects.for_organization(organization)
    # A suspicion must never inflate the reported vacancy figure.
    assert list(scoped.vacant()) == [vacant]
    assert suspected not in scoped.vacant()
    assert list(scoped.confirmed()) == [vacant]
    assert critical in scoped.critical()
    assert list(scoped.public()) == [published]
    assert suspected in scoped.open_checks()


@pytest.mark.django_db
def test_search_covers_internal_fields_only_when_asked(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="search")
    Property.objects.create(
        organization=organization,
        street="Marktplatz",
        public_description="Empty shop on the ground floor",
        internal_description="Heirs unknown, land registry checked",
    )
    scoped = Property.objects.for_organization(organization)

    assert search_properties(scoped, "Marktplatz").count() == 1
    assert search_properties(scoped, "shop").count() == 1
    # Internal wording must not be findable from a public surface.
    assert search_properties(scoped, "Heirs").count() == 0
    assert search_properties(scoped, "Heirs", include_internal=True).count() == 1
    # An empty query leaves the queryset untouched.
    assert search_properties(scoped, "").count() == scoped.count()


# --- Parcels ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_record_can_span_several_parcels(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="parcel")
    record = Property.objects.create(organization=organization)
    first = Parcel.objects.create(
        organization=organization, cadastral_district="Reichenbach", parcel_number="112/3"
    )
    second = Parcel.objects.create(
        organization=organization, cadastral_district="Reichenbach", parcel_number="112/4"
    )
    record.parcels.set([first, second])
    assert record.parcels.count() == 2
    assert first.properties.first() == record
    assert first.label == "Reichenbach 112/3"


# --- Views -----------------------------------------------------------------


@pytest.mark.django_db
def test_records_are_isolated_between_municipalities(client, municipal_staff):
    user_a, org_a, _m_a = municipal_staff(username="staff_a")
    user_b, _org_b, _m_b = municipal_staff(username="staff_b")
    secret = Property.objects.create(
        organization=org_a, street="Geheimstraße", public_description="Only for A"
    )

    client.force_login(user_b)
    listing = client.get(reverse("properties:list"))
    assert listing.status_code == 200
    assert b"Geheimstra" not in listing.content
    assert client.get(secret.get_absolute_url()).status_code == 404

    client.force_login(user_a)
    assert client.get(secret.get_absolute_url()).status_code == 200


@pytest.mark.django_db
def test_citizens_cannot_reach_the_records(client, make_user, municipal_staff):
    municipal_staff(username="staff_c")
    citizen = make_user(username="citizen_p")
    client.force_login(citizen)
    assert client.get(reverse("properties:list")).status_code == 403


@pytest.mark.django_db
def test_external_body_may_read_but_not_edit(client, municipal_staff):
    _staff, organization, _municipality = municipal_staff(username="staff_d")
    agency, _org, _mun = municipal_staff(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_p"
    )
    record = Property.objects.create(organization=organization, city="Town")

    client.force_login(agency)
    assert client.get(reverse("properties:list")).status_code == 200
    assert client.get(record.get_absolute_url()).status_code == 200
    assert client.get(reverse("properties:create")).status_code == 403
    assert client.post(
        reverse("properties:transition", args=[record.pk]),
        {"status": RecordStatus.PRE_CHECK.value},
    ).status_code == 403


@pytest.mark.django_db
def test_staff_can_create_a_record_through_the_form(client, municipal_staff):
    user, organization, municipality = municipal_staff(username="creator")
    district = District.objects.create(municipality=municipality, name="Centre")

    client.force_login(user)
    response = client.post(
        reverse("properties:create"),
        {
            "district": district.pk,
            "street": "Zwickauer Straße",
            "house_number": "4",
            "postal_code": "08468",
            "city": "Reichenbach im Vogtland",
            "property_type": PropertyType.RESIDENTIAL.value,
            "last_known_use": "housing",
            "condition": ConditionGrade.MAJOR_REPAIR.value,
            "condition_source": AssessmentSource.STAFF_ASSESSMENT.value,
            "priority": Priority.HIGH.value,
            "recorded_on": "2026-08-01",
            "public_description": "Vacant since 2019",
            "internal_description": "Owner contacted twice",
        },
    )
    assert response.status_code == 302
    record = Property.objects.get(organization=organization, street="Zwickauer Straße")
    assert record.created_by == user
    assert record.district == district
    assert record.reference


@pytest.mark.django_db
def test_the_edit_form_cannot_change_status_or_occupancy(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    response = client.get(reverse("properties:edit", args=[obj.pk]))
    form_fields = response.context["form"].fields
    assert "status" not in form_fields
    assert "vacancy_status" not in form_fields


@pytest.mark.django_db
def test_status_change_through_the_view_is_logged(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    response = client.post(
        reverse("properties:transition", args=[obj.pk]),
        {"status": RecordStatus.PRE_CHECK.value, "reason": "Report looks plausible"},
    )
    assert response.status_code == 302
    obj.refresh_from_db()
    assert obj.status == RecordStatus.PRE_CHECK
    transition = obj.status_transitions.first()
    assert transition.actor == user
    assert transition.reason == "Report looks plausible"


@pytest.mark.django_db
def test_an_impossible_status_change_through_the_view_is_refused(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    response = client.post(
        reverse("properties:transition", args=[obj.pk]),
        {"status": RecordStatus.CONFIRMED.value},
    )
    assert response.status_code == 302
    obj.refresh_from_db()
    assert obj.status == RecordStatus.NEW
    assert obj.status_transitions.count() == 0


@pytest.mark.django_db
def test_publication_is_a_deliberate_action(client, record):
    user, _organization, _municipality, obj = record
    assert obj.is_public is False
    client.force_login(user)

    client.post(reverse("properties:publication", args=[obj.pk]))
    obj.refresh_from_db()
    assert obj.is_public is True

    client.post(reverse("properties:publication", args=[obj.pk]))
    obj.refresh_from_db()
    assert obj.is_public is False


@pytest.mark.django_db
def test_occupancy_view_extends_the_history(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    response = client.post(
        reverse("properties:occupancy", args=[obj.pk]),
        {"vacancy_status": VacancyStatus.VACANT.value, "source": "Site visit"},
    )
    assert response.status_code == 302
    obj.refresh_from_db()
    assert obj.vacancy_status == VacancyStatus.VACANT
    assert obj.vacancy_periods.count() == 1


@pytest.mark.django_db
def test_damage_can_be_added_and_removed_through_views(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    client.post(
        reverse("properties:damage_create", args=[obj.pk]),
        {
            "damage_type": DamageType.ROOF.value,
            "severity": "severe",
            "source": AssessmentSource.STAFF_ASSESSMENT.value,
        },
    )
    damage = obj.damages.get()
    client.post(reverse("properties:damage_delete", args=[obj.pk, damage.pk]))
    assert obj.damages.count() == 0


@pytest.mark.django_db
def test_list_filters_narrow_the_result(client, municipal_staff):
    user, organization, municipality = municipal_staff(username="filter")
    centre = District.objects.create(municipality=municipality, name="Centre")
    Property.objects.create(
        organization=organization, district=centre, street="Innenstadtweg"
    )
    Property.objects.create(organization=organization, street="Randweg")

    client.force_login(user)
    body = client.get(reverse("properties:list"), {"district": centre.pk}).content.decode()
    assert "Innenstadtweg" in body
    assert "Randweg" not in body


@pytest.mark.django_db
def test_history_view_lists_status_changes(client, record):
    user, _organization, _municipality, obj = record
    obj.transition_to(RecordStatus.PRE_CHECK, actor=user, reason="Checked the file")
    client.force_login(user)
    response = client.get(reverse("properties:history", args=[obj.pk]))
    assert response.status_code == 200
    assert b"Checked the file" in response.content
