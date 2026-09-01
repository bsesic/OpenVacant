import pytest
from django.urls import reverse

from apps.inspections.models import Inspection, InspectionKind, InspectionResult
from apps.properties.choices import (
    AssessmentSource,
    ConditionGrade,
    DamageType,
    RecordStatus,
    VacancyStatus,
)
from apps.properties.models import Property
from apps.workflows.models import Task, TaskType
from organizations.models import Role


@pytest.fixture
def record(municipal_staff):
    user, organization, municipality = municipal_staff(username="inspector")
    obj = Property.objects.create(
        organization=organization, street="Weberstraße", city="Reichenbach"
    )
    return user, organization, municipality, obj


def _payload(**overrides):
    payload = {
        "kind": InspectionKind.ON_SITE.value,
        "result": InspectionResult.CONFIRMED.value,
        "inspected_on": "2026-08-10",
        "observed_vacancy_status": VacancyStatus.VACANT.value,
        "observed_condition": ConditionGrade.MAJOR_REPAIR.value,
        "findings": "Letterbox sealed, no curtains, garden overgrown.",
    }
    payload.update(overrides)
    return payload


# --- Applying findings -----------------------------------------------------


@pytest.mark.django_db
def test_staff_verification_walks_the_record_to_confirmed(client, record):
    user, _organization, _municipality, obj = record
    assert obj.status == RecordStatus.NEW

    client.force_login(user)
    response = client.post(reverse("inspections:create", args=[obj.pk]), _payload())
    assert response.status_code == 302

    obj.refresh_from_db()
    # The record must pass through the intermediate steps, not jump.
    statuses = [t.to_status for t in obj.status_transitions.order_by("created_at")]
    assert statuses == [
        RecordStatus.PRE_CHECK,
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.CONFIRMED,
    ]
    assert obj.status == RecordStatus.CONFIRMED
    assert obj.vacancy_status == VacancyStatus.VACANT
    assert obj.condition == ConditionGrade.MAJOR_REPAIR
    assert obj.condition_source == AssessmentSource.STAFF_ASSESSMENT
    assert obj.last_checked_on.isoformat() == "2026-08-10"


@pytest.mark.django_db
def test_a_contributor_verification_stops_short_of_confirming(client, make_member, record):
    _staff, organization, _municipality, obj = record
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="helper_v"
    )

    client.force_login(contributor)
    response = client.post(reverse("inspections:create", args=[obj.pk]), _payload())
    assert response.status_code == 302

    obj.refresh_from_db()
    inspection = Inspection.objects.get()
    assert inspection.result == InspectionResult.CONFIRMED
    assert inspection.confirms_the_record is False
    # Confirmed vacancy is an official statement, so it waits for the
    # administration; the observation itself is kept.
    assert obj.status == RecordStatus.ON_SITE_CHECK
    assert obj.vacancy_status == VacancyStatus.VACANT
    assert obj.condition_source == AssessmentSource.CITIZEN_OBSERVATION
    # And the administration is left a task rather than a silent record.
    assert Task.objects.filter(property=obj, task_type=TaskType.CHECK_PROPERTY).exists()


@pytest.mark.django_db
def test_not_confirmed_result_moves_the_record_accordingly(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    client.post(
        reverse("inspections:create", args=[obj.pk]),
        _payload(
            result=InspectionResult.NOT_CONFIRMED.value,
            observed_vacancy_status=VacancyStatus.IN_USE.value,
        ),
    )
    obj.refresh_from_db()
    assert obj.status == RecordStatus.NOT_CONFIRMED
    assert obj.vacancy_status == VacancyStatus.IN_USE
    assert not obj.is_vacant


@pytest.mark.django_db
def test_unclear_result_keeps_the_record_open(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    client.post(
        reverse("inspections:create", args=[obj.pk]),
        _payload(
            result=InspectionResult.UNCLEAR.value,
            observed_vacancy_status=VacancyStatus.UNKNOWN.value,
        ),
    )
    obj.refresh_from_db()
    assert obj.status == RecordStatus.UNCLEAR
    assert obj.needs_check


@pytest.mark.django_db
def test_observed_damage_is_recorded_with_its_weight(client, record):
    user, _organization, _municipality, obj = record
    client.force_login(user)
    payload = _payload()
    payload["observed_damage_types"] = [DamageType.ROOF.value, DamageType.MOISTURE.value]
    client.post(reverse("inspections:create", args=[obj.pk]), payload)

    assert obj.damages.count() == 2
    assert obj.damages.first().source == AssessmentSource.STAFF_ASSESSMENT
    inspection = Inspection.objects.get()
    assert len(inspection.damage_labels) == 2


@pytest.mark.django_db
def test_unknown_observations_do_not_overwrite_what_is_known(client, record):
    user, _organization, _municipality, obj = record
    obj.condition = ConditionGrade.GOOD
    obj.condition_source = AssessmentSource.EXPERT_REPORT
    obj.save()

    client.force_login(user)
    client.post(
        reverse("inspections:create", args=[obj.pk]),
        _payload(
            observed_condition=ConditionGrade.UNKNOWN.value,
            observed_vacancy_status=VacancyStatus.UNKNOWN.value,
        ),
    )
    obj.refresh_from_db()
    # "Not assessed" is not a finding, so the expert assessment survives.
    assert obj.condition == ConditionGrade.GOOD
    assert obj.condition_source == AssessmentSource.EXPERT_REPORT


@pytest.mark.django_db
def test_the_role_at_the_time_is_frozen_on_the_inspection(client, make_member, record):
    _staff, organization, _municipality, obj = record
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="promoted"
    )
    client.force_login(contributor)
    client.post(reverse("inspections:create", args=[obj.pk]), _payload())

    inspection = Inspection.objects.get()
    assert inspection.inspector_role == Role.VERIFIED_CONTRIBUTOR

    # Promoting the person later must not rewrite a past inspection.
    membership = organization.memberships.get(user=contributor)
    membership.role = Role.BUILDING_AUTHORITY
    membership.save(update_fields=["role"])
    inspection.refresh_from_db()
    assert inspection.inspector_role == Role.VERIFIED_CONTRIBUTOR
    assert inspection.confirms_the_record is False


@pytest.mark.django_db
def test_an_archived_record_is_not_reopened_by_a_verification(record):
    user, organization, _municipality, obj = record
    obj.transition_to(RecordStatus.ARCHIVED, actor=user)
    before = obj.status_transitions.count()

    inspection = Inspection.objects.create(
        organization=organization,
        property=obj,
        result=InspectionResult.CONFIRMED,
        inspector=user,
        inspector_role=Role.BUILDING_AUTHORITY,
    )
    inspection.apply_to_property(actor=user)

    obj.refresh_from_db()
    assert obj.status == RecordStatus.ARCHIVED
    assert obj.status_transitions.count() == before


# --- Permissions -----------------------------------------------------------


@pytest.mark.django_db
def test_external_body_cannot_verify(client, make_member, record):
    _staff, organization, _municipality, obj = record
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_i"
    )
    client.force_login(agency)
    assert client.get(reverse("inspections:create", args=[obj.pk])).status_code == 403


@pytest.mark.django_db
def test_citizens_cannot_verify(client, make_user, record):
    _staff, _organization, _municipality, obj = record
    citizen = make_user(username="passerby")
    client.force_login(citizen)
    assert client.get(reverse("inspections:create", args=[obj.pk])).status_code == 403


@pytest.mark.django_db
def test_verifications_are_isolated_between_municipalities(client, municipal_staff, record):
    _staff, _organization, _municipality, obj = record
    other, _org, _mun = municipal_staff(username="other_inspector")
    client.force_login(other)
    assert client.get(reverse("inspections:create", args=[obj.pk])).status_code == 404
