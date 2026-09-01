"""Awarding points and badges.

Called from the report and verification flows. Every entry point is a no-op when
the municipality has the participation module switched off, so a municipality
that wants nothing to do with gamification never accumulates the data.
"""

from django.db import transaction

from apps.municipalities.models import Module
from apps.participation.models import (
    POINT_VALUES,
    Award,
    Badge,
    ContributorProfile,
    PointEntry,
    PointReason,
)


def _module_enabled(organization):
    municipality = getattr(organization, "municipality", None)
    if municipality is None:
        return False
    return municipality.module_enabled(Module.PARTICIPATION)


def profile_for(organization, user):
    """The contributor profile for this user and municipality, created on demand.

    Returns None for anonymous contributions: there is nobody to credit, which is
    the trade-off a reporter accepts by staying anonymous.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if not _module_enabled(organization):
        return None
    profile, _created = ContributorProfile.objects.get_or_create(
        organization=organization, user=user
    )
    return profile


@transaction.atomic
def award(profile, reason, points=None, note="", actor=None):
    """Give points, log why, recompute the level and check the badges."""
    if profile is None:
        return None
    value = POINT_VALUES.get(reason, 0) if points is None else points
    if not value:
        return None

    entry = PointEntry.objects.create(
        profile=profile, reason=reason, points=value, note=note, awarded_by=actor
    )
    profile.points = max(0, profile.points + value)
    profile.recompute_level()
    profile.save(update_fields=["points", "level", "updated_at"])
    refresh_badges(profile)
    return entry


def refresh_badges(profile):
    """Grant any badge whose conditions the profile now meets.

    Badges are never taken away: they record something that happened.
    """
    held = set(profile.awards.values_list("badge_id", flat=True))
    granted = []
    for badge in Badge.objects.filter(is_active=True):
        if badge.pk in held or not badge.is_earned_by(profile):
            continue
        Award.objects.create(profile=profile, badge=badge)
        granted.append(badge)
    return granted


def record_report_accepted(report, actor=None):
    """A report was taken into the register."""
    profile = profile_for(report.organization, report.submitted_by)
    if profile is None:
        return None
    profile.reports_accepted += 1
    profile.save(update_fields=["reports_accepted", "updated_at"])
    return award(
        profile,
        PointReason.REPORT_ACCEPTED,
        note=report.reference,
        actor=actor,
    )


def record_report_confirmed(report, actor=None):
    """The object a report described turned out to be a confirmed vacancy.

    This is the award that matters: it rewards being right, not being prolific.
    """
    profile = profile_for(report.organization, report.submitted_by)
    if profile is None:
        return None
    profile.reports_confirmed += 1
    profile.save(update_fields=["reports_confirmed", "updated_at"])
    return award(
        profile, PointReason.REPORT_CONFIRMED, note=report.reference, actor=actor
    )


def record_inspection(inspection):
    """A verification was carried out on site."""
    profile = profile_for(inspection.organization, inspection.inspector)
    if profile is None:
        return None
    profile.inspections_completed += 1
    profile.save(update_fields=["inspections_completed", "updated_at"])
    return award(
        profile,
        PointReason.INSPECTION_COMPLETED,
        note=str(inspection.property.reference),
    )


def record_task_completed(task):
    """A task assigned to a contributor was completed."""
    profile = profile_for(task.organization, task.assignee)
    if profile is None:
        return None
    profile.tasks_completed += 1
    profile.save(update_fields=["tasks_completed", "updated_at"])
    return award(profile, PointReason.TASK_COMPLETED, note=task.label)


def notify_confirmations_for(record, actor=None):
    """Credit the reporters of a record that has just been confirmed.

    A record can carry several reports; each identifiable reporter is credited
    once, which is why the confirmation counter lives on the profile.
    """
    entries = []
    for report in record.reports.all():
        entry = record_report_confirmed(report, actor=actor)
        if entry is not None:
            entries.append(entry)
    return entries
