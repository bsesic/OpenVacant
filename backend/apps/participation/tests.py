import pytest
from django.urls import reverse

from apps.inspections.models import Inspection, InspectionResult
from apps.municipalities.models import Module
from apps.participation.models import (
    POINT_VALUES,
    ActivityLevel,
    Award,
    Badge,
    ContributorProfile,
    PointEntry,
    PointReason,
)
from apps.participation.services import (
    award,
    profile_for,
    record_report_accepted,
    record_report_confirmed,
)
from apps.properties.choices import RecordStatus, VacancyStatus
from apps.properties.models import Property
from apps.reports.models import Report
from apps.workflows.models import Task
from organizations.models import Role


@pytest.fixture
def instance(make_municipality):
    return make_municipality(name="Reichenbach")


@pytest.fixture
def reporter(make_user):
    return make_user(username="engaged")


# --- Profiles --------------------------------------------------------------


@pytest.mark.django_db
def test_a_profile_is_created_on_demand(instance, reporter):
    profile = profile_for(instance.organization, reporter)
    assert profile is not None
    assert profile.points == 0
    assert profile.level == ActivityLevel.NEWCOMER
    # Calling again returns the same profile rather than a second one.
    assert profile_for(instance.organization, reporter) == profile
    assert ContributorProfile.objects.count() == 1


@pytest.mark.django_db
def test_anonymous_contributions_credit_nobody(instance):
    """Staying anonymous means giving up the credit, which is the trade-off."""
    assert profile_for(instance.organization, None) is None


@pytest.mark.django_db
def test_nothing_is_recorded_when_the_module_is_off(instance, reporter):
    instance.set_module(Module.PARTICIPATION, False)
    assert profile_for(instance.organization, reporter) is None
    assert ContributorProfile.objects.count() == 0


@pytest.mark.django_db
def test_reputation_is_scoped_to_the_municipality(instance, reporter, make_municipality):
    """Reliability is what one administration observed; it is not portable."""
    other = make_municipality(name="Elsewhere")
    here = profile_for(instance.organization, reporter)
    there = profile_for(other.organization, reporter)
    assert here != there

    award(here, PointReason.REPORT_CONFIRMED)
    there.refresh_from_db()
    assert there.points == 0


# --- Points and levels -----------------------------------------------------


@pytest.mark.django_db
def test_submitting_a_report_earns_nothing_by_itself(instance, reporter):
    """Rewarding submissions would reward volume, which is the failure mode."""
    report = Report.objects.create(
        organization=instance.organization, submitted_by=reporter, city="Town"
    )
    profile = profile_for(instance.organization, reporter)
    assert profile.points == 0
    assert report.pk
    assert PointEntry.objects.count() == 0


@pytest.mark.django_db
def test_being_right_is_worth_more_than_being_accepted(instance, reporter):
    report = Report.objects.create(
        organization=instance.organization, submitted_by=reporter, city="Town"
    )
    record_report_accepted(report)
    profile = profile_for(instance.organization, reporter)
    profile.refresh_from_db()
    accepted_points = profile.points
    assert accepted_points == POINT_VALUES[PointReason.REPORT_ACCEPTED]
    assert profile.reports_accepted == 1

    record_report_confirmed(report)
    profile.refresh_from_db()
    confirmed_points = profile.points - accepted_points
    assert confirmed_points == POINT_VALUES[PointReason.REPORT_CONFIRMED]
    assert confirmed_points > accepted_points
    assert profile.reports_confirmed == 1


@pytest.mark.django_db
def test_every_total_can_be_explained(instance, reporter):
    profile = profile_for(instance.organization, reporter)
    award(profile, PointReason.MANUAL, points=30, note="Helped survey a quarter")
    entries = list(profile.point_entries.all())
    assert len(entries) == 1
    assert entries[0].points == 30
    assert entries[0].note == "Helped survey a quarter"
    assert sum(entry.points for entry in entries) == profile.points


@pytest.mark.django_db
def test_levels_follow_the_thresholds(instance, reporter):
    profile = profile_for(instance.organization, reporter)
    award(profile, PointReason.MANUAL, points=20)
    profile.refresh_from_db()
    assert profile.level == ActivityLevel.CONTRIBUTOR

    award(profile, PointReason.MANUAL, points=200)
    profile.refresh_from_db()
    assert profile.level == ActivityLevel.TRUSTED

    award(profile, PointReason.MANUAL, points=300)
    profile.refresh_from_db()
    assert profile.level == ActivityLevel.EXPERT


@pytest.mark.django_db
def test_points_never_go_below_zero(instance, reporter):
    profile = profile_for(instance.organization, reporter)
    award(profile, PointReason.MANUAL, points=10)
    award(profile, PointReason.MANUAL, points=-50, note="Correction")
    profile.refresh_from_db()
    assert profile.points == 0


@pytest.mark.django_db
def test_reliability_needs_a_track_record(instance, reporter):
    """One out of one is not a track record, and 100% would mislead."""
    profile = profile_for(instance.organization, reporter)
    profile.reports_accepted = 1
    profile.reports_confirmed = 1
    assert profile.reliability is None

    profile.reports_accepted = 4
    profile.reports_confirmed = 3
    assert profile.reliability == 0.75


# --- Badges ----------------------------------------------------------------


@pytest.mark.django_db
def test_badges_are_granted_when_earned_and_never_taken_away(instance, reporter):
    badge = Badge.objects.create(key="first-steps", name="First steps", required_points=10)
    strict = Badge.objects.create(
        key="reliable", name="Reliable", required_confirmed_reports=3
    )
    profile = profile_for(instance.organization, reporter)

    award(profile, PointReason.MANUAL, points=10)
    assert Award.objects.filter(profile=profile, badge=badge).exists()
    assert not Award.objects.filter(profile=profile, badge=strict).exists()

    # A later correction does not withdraw what happened.
    award(profile, PointReason.MANUAL, points=-10)
    assert Award.objects.filter(profile=profile, badge=badge).exists()


@pytest.mark.django_db
def test_a_badge_is_granted_only_once(instance, reporter):
    Badge.objects.create(key="starter", name="Starter", required_points=5)
    profile = profile_for(instance.organization, reporter)
    award(profile, PointReason.MANUAL, points=10)
    award(profile, PointReason.MANUAL, points=10)
    assert Award.objects.filter(profile=profile).count() == 1


@pytest.mark.django_db
def test_inactive_badges_are_not_granted(instance, reporter):
    Badge.objects.create(key="retired", name="Retired", required_points=1, is_active=False)
    profile = profile_for(instance.organization, reporter)
    award(profile, PointReason.MANUAL, points=10)
    assert Award.objects.count() == 0


# --- Integration with the domain flows ------------------------------------


@pytest.mark.django_db
def test_accepting_a_report_credits_its_reporter(client, instance, reporter, make_member):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="part_staff"
    )
    report = Report.objects.create(
        organization=instance.organization, submitted_by=reporter, city="Town"
    )

    client.force_login(staff)
    client.post(reverse("reports:accept", args=[report.pk]))

    profile = ContributorProfile.objects.get(user=reporter)
    assert profile.reports_accepted == 1
    assert profile.points == POINT_VALUES[PointReason.REPORT_ACCEPTED]


@pytest.mark.django_db
def test_confirming_a_record_credits_the_reporters_who_were_right(
    client, instance, reporter, make_member
):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="part_staff2"
    )
    report = Report.objects.create(
        organization=instance.organization, submitted_by=reporter, city="Town"
    )
    client.force_login(staff)
    client.post(reverse("reports:accept", args=[report.pk]))
    record = Property.objects.get()

    client.post(
        reverse("inspections:create", args=[record.pk]),
        {
            "kind": "on_site",
            "result": InspectionResult.CONFIRMED.value,
            "inspected_on": "2026-08-15",
            "observed_vacancy_status": VacancyStatus.VACANT.value,
            "observed_condition": "major_repair",
        },
    )
    record.refresh_from_db()
    assert record.status == RecordStatus.CONFIRMED

    profile = ContributorProfile.objects.get(user=reporter)
    assert profile.reports_confirmed == 1
    assert profile.points >= (
        POINT_VALUES[PointReason.REPORT_ACCEPTED]
        + POINT_VALUES[PointReason.REPORT_CONFIRMED]
    )


@pytest.mark.django_db
def test_a_contributor_verification_credits_the_contributor(
    client, instance, make_member
):
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR,
        organization=instance.organization,
        username="part_helper",
    )
    record = Property.objects.create(organization=instance.organization, city="Town")

    client.force_login(contributor)
    client.post(
        reverse("inspections:create", args=[record.pk]),
        {
            "kind": "on_site",
            "result": InspectionResult.UNCLEAR.value,
            "inspected_on": "2026-08-15",
            "observed_vacancy_status": VacancyStatus.UNKNOWN.value,
            "observed_condition": "unknown",
        },
    )
    profile = ContributorProfile.objects.get(user=contributor)
    assert profile.inspections_completed == 1
    assert profile.points == POINT_VALUES[PointReason.INSPECTION_COMPLETED]
    assert Inspection.objects.count() == 1


@pytest.mark.django_db
def test_completing_a_task_credits_its_assignee(instance, make_member):
    contributor, _org = make_member(
        role=Role.VERIFIED_CONTRIBUTOR,
        organization=instance.organization,
        username="part_helper2",
    )
    task = Task.objects.create(organization=instance.organization, assignee=contributor)
    task.complete(actor=contributor)

    profile = ContributorProfile.objects.get(user=contributor)
    assert profile.tasks_completed == 1
    assert profile.points == POINT_VALUES[PointReason.TASK_COMPLETED]


@pytest.mark.django_db
def test_the_flows_still_work_with_participation_switched_off(
    client, instance, reporter, make_member
):
    instance.set_module(Module.PARTICIPATION, False)
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="part_staff3"
    )
    report = Report.objects.create(
        organization=instance.organization, submitted_by=reporter, city="Town"
    )
    client.force_login(staff)
    response = client.post(reverse("reports:accept", args=[report.pk]))
    assert response.status_code == 302
    assert Property.objects.count() == 1
    assert ContributorProfile.objects.count() == 0


@pytest.mark.django_db
def test_nobody_is_named_publicly_without_agreeing(instance, reporter):
    profile = profile_for(instance.organization, reporter)
    assert profile.wants_recognition is False
    assert profile.display_name == ""
