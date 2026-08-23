import datetime

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.urls import reverse

from apps.municipalities.models import District
from apps.properties.choices import ConditionGrade, PropertyType, RecordStatus, VacancyStatus
from apps.properties.models import Property
from apps.reports.models import Report
from apps.statistics.models import KeyFigureSnapshot
from apps.statistics.services import breakdowns, key_figures, monthly_series, take_snapshot
from apps.workflows.models import Task
from organizations.models import Role


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="stats_staff")
    return user, organization, municipality


def _confirm(record, actor=None):
    """Walk a record through the workflow to confirmed."""
    for status in (
        RecordStatus.PRE_CHECK,
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.CONFIRMED,
    ):
        record.transition_to(status, actor=actor)
    return record


# --- Key figures -----------------------------------------------------------


@pytest.mark.django_db
def test_suspected_vacancy_is_counted_separately_from_confirmed(setup):
    _user, organization, _municipality = setup
    suspected = Property.objects.create(organization=organization)
    suspected.set_vacancy_status(VacancyStatus.SUSPECTED_VACANT)
    vacant = Property.objects.create(organization=organization)
    vacant.set_vacancy_status(VacancyStatus.VACANT)

    figures = key_figures(organization)
    # Reporting them together would overstate the problem.
    assert figures["confirmed_vacancies"] == 1
    assert figures["suspected_vacancies"] == 1
    assert figures["total_records"] == 2


@pytest.mark.django_db
def test_figures_cover_the_specification_headlines(setup):
    user, organization, municipality = setup
    district = District.objects.create(municipality=municipality, name="Centre")

    listed = Property.objects.create(
        organization=organization, district=district, is_heritage_protected=True
    )
    listed.set_vacancy_status(VacancyStatus.VACANT)
    _confirm(listed, actor=user)

    Property.objects.create(
        organization=organization, condition=ConditionGrade.COLLAPSE_RISK
    )
    Property.objects.create(organization=organization, is_public=True)
    Report.objects.create(organization=organization, city="Town")
    Task.objects.create(
        organization=organization,
        due_on=datetime.date.today() - datetime.timedelta(days=2),
    )

    figures = key_figures(organization)
    assert figures["confirmed_records"] == 1
    assert figures["confirmed_vacancies"] == 1
    assert figures["heritage_vacancies"] == 1
    assert figures["critical_records"] == 1
    assert figures["published_records"] == 1
    assert figures["open_reports"] == 1
    assert figures["open_tasks"] == 1
    assert figures["overdue_tasks"] == 1
    assert figures["open_checks"] >= 1


@pytest.mark.django_db
def test_figures_are_scoped_to_the_municipality(setup, make_municipality):
    _user, organization, _municipality = setup
    other = make_municipality(name="Elsewhere")
    mine = Property.objects.create(organization=organization)
    mine.set_vacancy_status(VacancyStatus.VACANT)
    theirs = Property.objects.create(organization=other.organization)
    theirs.set_vacancy_status(VacancyStatus.VACANT)

    assert key_figures(organization)["confirmed_vacancies"] == 1
    assert key_figures(other.organization)["confirmed_vacancies"] == 1


# --- Breakdowns ------------------------------------------------------------


@pytest.mark.django_db
def test_breakdowns_split_vacancy_the_required_ways(setup):
    _user, organization, municipality = setup
    centre = District.objects.create(municipality=municipality, name="Centre")

    for property_type in (PropertyType.RESIDENTIAL, PropertyType.RETAIL):
        record = Property.objects.create(
            organization=organization,
            district=centre,
            property_type=property_type,
            condition=ConditionGrade.MAJOR_REPAIR,
        )
        record.set_vacancy_status(VacancyStatus.VACANT)

    # Not vacant, so it must not appear in the vacancy breakdowns.
    Property.objects.create(
        organization=organization, district=centre, vacancy_status=VacancyStatus.IN_USE
    )

    parts = breakdowns(organization)
    assert parts["by_district"] == [{"label": "Centre", "count": 2}]
    counts = {entry["key"]: entry["count"] for entry in parts["by_property_type"]}
    assert counts[PropertyType.RESIDENTIAL] == 1
    assert counts[PropertyType.RETAIL] == 1
    assert counts[PropertyType.OFFICE] == 0

    conditions = {entry["key"]: entry["count"] for entry in parts["by_condition"]}
    assert conditions[ConditionGrade.MAJOR_REPAIR] == 2
    # A zero row is a result in itself, so it is kept rather than dropped.
    assert conditions[ConditionGrade.DANGEROUS] == 0


@pytest.mark.django_db
def test_records_without_a_district_are_labelled_not_dropped(setup):
    _user, organization, _municipality = setup
    record = Property.objects.create(organization=organization)
    record.set_vacancy_status(VacancyStatus.VACANT)

    parts = breakdowns(organization)
    assert parts["by_district"][0]["count"] == 1
    assert parts["by_district"][0]["label"]


# --- Time series -----------------------------------------------------------


@pytest.mark.django_db
def test_monthly_series_covers_every_month_including_empty_ones(setup):
    _user, organization, _municipality = setup
    Report.objects.create(organization=organization, city="Town")

    series = monthly_series(organization, months=6)
    assert len(series) >= 6
    assert series[-1]["new"] == 1
    # An empty month is a data point, not a gap.
    assert all("new" in point and "resolved" in point for point in series)


@pytest.mark.django_db
def test_resolved_counts_records_leaving_the_problem(setup):
    user, organization, _municipality = setup
    record = Property.objects.create(organization=organization)
    record.transition_to(RecordStatus.PRE_CHECK, actor=user)
    record.transition_to(RecordStatus.NOT_CONFIRMED, actor=user)

    series = monthly_series(organization, months=3)
    assert series[-1]["resolved"] == 1


# --- Snapshots -------------------------------------------------------------


@pytest.mark.django_db
def test_a_snapshot_stores_the_figures_of_the_day(setup):
    _user, organization, _municipality = setup
    record = Property.objects.create(organization=organization)
    record.set_vacancy_status(VacancyStatus.VACANT)

    snapshot = take_snapshot(organization)
    assert snapshot.total_records == 1
    assert snapshot.confirmed_vacancies == 1
    assert "breakdowns" in snapshot.figures


@pytest.mark.django_db
def test_taking_a_snapshot_twice_replaces_the_days_entry(setup):
    _user, organization, _municipality = setup
    take_snapshot(organization)
    Property.objects.create(organization=organization)
    take_snapshot(organization)

    assert KeyFigureSnapshot.objects.count() == 1
    assert KeyFigureSnapshot.objects.get().total_records == 1


@pytest.mark.django_db
def test_snapshots_preserve_history_the_records_cannot(setup):
    """A demolished record leaves no trace of what last month looked like."""
    _user, organization, _municipality = setup
    record = Property.objects.create(organization=organization)
    record.set_vacancy_status(VacancyStatus.VACANT)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    take_snapshot(organization, on=yesterday)

    record.set_vacancy_status(VacancyStatus.DEMOLISHED)
    assert key_figures(organization)["confirmed_vacancies"] == 0
    assert KeyFigureSnapshot.objects.get(taken_on=yesterday).confirmed_vacancies == 1


@pytest.mark.django_db
def test_snapshot_command_runs_for_every_municipality(setup, make_municipality):
    _user, organization, _municipality = setup
    make_municipality(name="Second town")
    call_command("snapshot_statistics")
    assert KeyFigureSnapshot.objects.count() == 2


@pytest.mark.django_db
def test_snapshot_task_covers_all_municipalities(setup, make_municipality):
    from apps.statistics.tasks import take_daily_snapshots

    make_municipality(name="Third town")
    assert take_daily_snapshots() == 2


# --- Dashboard -------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_renders_for_internal_users(client, setup):
    user, organization, _municipality = setup
    Property.objects.create(organization=organization, street="Dashboardweg")
    client.force_login(user)
    response = client.get(reverse("statistics:dashboard"))
    assert response.status_code == 200
    assert response.context["figures"]["total_records"] == 1


@pytest.mark.django_db
def test_citizens_cannot_see_the_dashboard(client, setup, make_user):
    citizen = make_user(username="citizen_s")
    client.force_login(citizen)
    assert client.get(reverse("statistics:dashboard")).status_code == 403


@pytest.mark.django_db
def test_external_body_may_see_the_dashboard(client, setup, make_member):
    _user, organization, _municipality = setup
    agency, _org = make_member(
        role=Role.EXTERNAL_AGENCY, organization=organization, username="landkreis_s"
    )
    client.force_login(agency)
    assert client.get(reverse("statistics:dashboard")).status_code == 200


@pytest.mark.django_db
def test_dashboard_map_includes_unpublished_records_but_no_internal_text(client, setup):
    user, organization, _municipality = setup
    Property.objects.create(
        organization=organization,
        street="Nichtveroeffentlicht",
        location=Point(12.3, 50.6, srid=4326),
        is_public=False,
        internal_description="Heirs unknown, land registry checked",
    )
    client.force_login(user)
    response = client.get(reverse("statistics:map_data"))
    body = response.content.decode()

    assert response.json()["features"][0]["properties"]["is_public"] is False
    # Staff see the object, but the map popup is not the place for case notes.
    assert "Heirs unknown" not in body


@pytest.mark.django_db
def test_dashboard_map_filters_narrow_the_result(client, setup):
    user, organization, _municipality = setup
    Property.objects.create(
        organization=organization,
        location=Point(12.3, 50.6, srid=4326),
        condition=ConditionGrade.COLLAPSE_RISK,
    )
    Property.objects.create(
        organization=organization,
        location=Point(12.31, 50.61, srid=4326),
        condition=ConditionGrade.GOOD,
    )
    client.force_login(user)
    payload = client.get(
        reverse("statistics:map_data"), {"condition": ConditionGrade.COLLAPSE_RISK.value}
    ).json()
    assert len(payload["features"]) == 1


@pytest.mark.django_db
def test_dashboard_map_is_scoped_to_the_municipality(client, setup, make_municipality):
    user, _organization, _municipality = setup
    other = make_municipality(name="Elsewhere")
    Property.objects.create(
        organization=other.organization, location=Point(12.3, 50.6, srid=4326)
    )
    client.force_login(user)
    assert client.get(reverse("statistics:map_data")).json()["features"] == []


@pytest.mark.django_db
def test_key_figures_export_is_csv(client, setup):
    user, organization, _municipality = setup
    record = Property.objects.create(organization=organization)
    record.set_vacancy_status(VacancyStatus.VACANT)

    client.force_login(user)
    response = client.get(reverse("statistics:export"))
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert "attachment" in response["Content-Disposition"]
    body = response.content.decode()
    assert "confirmed_vacancies,1" in body
