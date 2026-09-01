import datetime

import pytest
from django.urls import reverse

from apps.properties.models import Property
from apps.reports.models import Report
from apps.workflows.models import Task, TaskStatus, TaskType, ensure_task
from organizations.models import Role


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="planner_w")
    record = Property.objects.create(organization=organization, street="Ringstraße")
    return user, organization, municipality, record


# --- Model behaviour -------------------------------------------------------


@pytest.mark.django_db
def test_label_falls_back_to_the_type(setup):
    _user, organization, _municipality, record = setup
    task = Task.objects.create(
        organization=organization, property=record, task_type=TaskType.VERIFY_HERITAGE
    )
    assert task.label == str(TaskType.VERIFY_HERITAGE.label)

    task.title = "Ask the heritage authority"
    task.save()
    assert task.label == "Ask the heritage authority"


@pytest.mark.django_db
def test_overdue_only_counts_open_tasks(setup):
    _user, organization, _municipality, record = setup
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    overdue = Task.objects.create(
        organization=organization, property=record, due_on=yesterday
    )
    done = Task.objects.create(
        organization=organization, property=record, due_on=yesterday, status=TaskStatus.DONE
    )

    assert overdue.is_overdue is True
    assert done.is_overdue is False
    scoped = Task.objects.for_organization(organization)
    assert list(scoped.overdue()) == [overdue]


@pytest.mark.django_db
def test_completing_claims_an_unassigned_task(setup):
    user, organization, _municipality, record = setup
    task = Task.objects.create(organization=organization, property=record)
    task.complete(actor=user, note="Checked on site")

    assert task.status == TaskStatus.DONE
    assert task.completed_at is not None
    assert task.completion_note == "Checked on site"
    # The record should show who actually did the work.
    assert task.assignee == user


@pytest.mark.django_db
def test_completing_keeps_an_existing_assignee(setup, make_member):
    _user, organization, _municipality, record = setup
    owner, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=organization, username="owner_w"
    )
    other, _org2 = make_member(
        role=Role.URBAN_PLANNING, organization=organization, username="other_w"
    )
    task = Task.objects.create(organization=organization, property=record, assignee=owner)
    task.complete(actor=other)
    assert task.assignee == owner


@pytest.mark.django_db
def test_ensure_task_does_not_duplicate_open_work(setup):
    _user, organization, _municipality, record = setup
    first = ensure_task(organization, TaskType.CHECK_PROPERTY, property=record)
    second = ensure_task(organization, TaskType.CHECK_PROPERTY, property=record)
    assert first == second
    assert Task.objects.count() == 1

    # Once it is done, the same task can legitimately come up again.
    first.complete()
    third = ensure_task(organization, TaskType.CHECK_PROPERTY, property=record)
    assert third != first
    assert Task.objects.count() == 2


@pytest.mark.django_db
def test_reopening_clears_the_completion(setup):
    _user, organization, _municipality, record = setup
    task = Task.objects.create(organization=organization, property=record)
    task.complete()
    task.reopen()
    assert task.status == TaskStatus.OPEN
    assert task.completed_at is None


# --- Views -----------------------------------------------------------------


@pytest.mark.django_db
def test_staff_see_the_whole_backlog(client, setup):
    user, organization, _municipality, record = setup
    Task.objects.create(organization=organization, property=record, title="Someone else's job")
    client.force_login(user)
    body = client.get(reverse("workflows:list")).content.decode()
    assert "Someone else&#x27;s job" in body or "Someone else's job" in body


@pytest.mark.django_db
def test_contributors_see_only_their_own_tasks(client, setup, make_member):
    _user, organization, _municipality, record = setup
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="helper_w"
    )
    Task.objects.create(organization=organization, property=record, title="Mine to do",
                        assignee=contributor)
    Task.objects.create(organization=organization, property=record, title="Not for me")

    client.force_login(contributor)
    body = client.get(reverse("workflows:list")).content.decode()
    assert "Mine to do" in body
    assert "Not for me" not in body


@pytest.mark.django_db
def test_contributors_cannot_create_tasks(client, setup, make_member):
    _user, organization, _municipality, _record = setup
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="helper_w2"
    )
    client.force_login(contributor)
    assert client.get(reverse("workflows:create")).status_code == 403


@pytest.mark.django_db
def test_contributors_cannot_close_someone_elses_task(client, setup, make_member):
    _user, organization, _municipality, record = setup
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="helper_w3"
    )
    task = Task.objects.create(organization=organization, property=record)

    client.force_login(contributor)
    response = client.post(reverse("workflows:complete", args=[task.pk]))
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == TaskStatus.OPEN

    task.assignee = contributor
    task.save(update_fields=["assignee"])
    client.post(reverse("workflows:complete", args=[task.pk]))
    task.refresh_from_db()
    assert task.status == TaskStatus.DONE


@pytest.mark.django_db
def test_assignee_choices_exclude_people_without_a_role(client, setup, make_user, make_member):
    user, organization, _municipality, _record = setup
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR, organization=organization, username="assignable"
    )
    outsider = make_user(username="outsider_w")

    client.force_login(user)
    form = client.get(reverse("workflows:create")).context["form"]
    assignees = list(form.fields["assignee"].queryset)
    assert contributor in assignees
    assert user in assignees
    assert outsider not in assignees


@pytest.mark.django_db
def test_tasks_are_isolated_between_municipalities(client, setup, municipal_staff):
    _user, organization, _municipality, record = setup
    Task.objects.create(organization=organization, property=record, title="Reichenbach only")
    other, _org, _mun = municipal_staff(username="other_planner")

    client.force_login(other)
    body = client.get(reverse("workflows:list")).content.decode()
    assert "Reichenbach only" not in body


@pytest.mark.django_db
def test_citizens_cannot_see_tasks(client, setup, make_user):
    citizen = make_user(username="curious_w")
    client.force_login(citizen)
    assert client.get(reverse("workflows:list")).status_code == 403


# --- Integration with reports ---------------------------------------------


@pytest.mark.django_db
def test_accepting_a_report_creates_the_check_task(client, setup):
    user, organization, _municipality, _record = setup
    report = Report.objects.create(organization=organization, city="Reichenbach")

    client.force_login(user)
    client.post(reverse("reports:accept", args=[report.pk]))

    created = Property.objects.exclude(street="Ringstraße").get()
    task = Task.objects.get(property=created)
    assert task.task_type == TaskType.CHECK_PROPERTY
    assert task.report == report
    assert task.is_open
