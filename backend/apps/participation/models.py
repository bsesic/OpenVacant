"""Contributor reputation.

Gamification is not required for the first version, but the data model has to be
ready for it. The shape here follows the one constraint the specification is
explicit about: quality and reliability count for more than volume. Points come
from reports that turned out to be right and from verifications actually carried
out — never from the act of submitting.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class ActivityLevel(models.IntegerChoices):
    """Levels, as thresholds rather than a formula, so they can be retuned."""

    NEWCOMER = 0, _("Newcomer")
    CONTRIBUTOR = 1, _("Contributor")
    REGULAR = 2, _("Regular")
    TRUSTED = 3, _("Trusted")
    EXPERT = 4, _("Expert")


LEVEL_THRESHOLDS = (
    (ActivityLevel.EXPERT, 500),
    (ActivityLevel.TRUSTED, 200),
    (ActivityLevel.REGULAR, 75),
    (ActivityLevel.CONTRIBUTOR, 20),
    (ActivityLevel.NEWCOMER, 0),
)


class PointReason(models.TextChoices):
    """What points are given for.

    Note what is absent: submitting a report earns nothing on its own. Rewarding
    submissions would reward volume, which is the failure mode the
    specification warns against.
    """

    REPORT_CONFIRMED = "report_confirmed", _("Report led to a confirmed object")
    REPORT_ACCEPTED = "report_accepted", _("Report accepted into the register")
    INSPECTION_COMPLETED = "inspection_completed", _("Verification carried out")
    TASK_COMPLETED = "task_completed", _("Task completed")
    MANUAL = "manual", _("Awarded by the administration")


# Weights. A verification carried out on site is worth more than a report that
# turned out to be right, which in turn is worth more than one merely accepted.
POINT_VALUES = {
    PointReason.REPORT_ACCEPTED: 5,
    PointReason.REPORT_CONFIRMED: 15,
    PointReason.INSPECTION_COMPLETED: 20,
    PointReason.TASK_COMPLETED: 10,
}


class ContributorProfile(OrganizationOwnedModel):
    """A citizen's standing with one municipality.

    Scoped to the municipality rather than global: reliability is something a
    particular administration has observed, and it is not theirs to export.
    """

    objects = OrgQuerySet.as_manager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contributor_profiles",
        verbose_name=_("user"),
    )
    points = models.PositiveIntegerField(_("points"), default=0)
    level = models.PositiveSmallIntegerField(
        _("level"), choices=ActivityLevel.choices, default=ActivityLevel.NEWCOMER
    )
    reports_accepted = models.PositiveIntegerField(_("reports accepted"), default=0)
    reports_confirmed = models.PositiveIntegerField(_("reports confirmed"), default=0)
    inspections_completed = models.PositiveIntegerField(_("verifications"), default=0)
    tasks_completed = models.PositiveIntegerField(_("tasks completed"), default=0)
    display_name = models.CharField(
        _("display name"),
        max_length=120,
        blank=True,
        help_text=_("Optional name for acknowledgements. Left empty means anonymous."),
    )
    wants_recognition = models.BooleanField(
        _("agrees to be named"),
        default=False,
        help_text=_("Nobody is named publicly without having agreed to it."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("contributor profile")
        verbose_name_plural = _("contributor profiles")
        ordering = ["-points"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_contributor_per_tenant"
            )
        ]

    def __str__(self):
        return self.display_name or str(self.user)

    @computed
    def level_label(self):
        return ActivityLevel(self.level).label

    @computed
    def reliability(self):
        """Share of accepted reports that were confirmed, or None if too few.

        Deliberately None below a handful of reports: one confirmed report out of
        one is not a track record, and presenting it as 100% would be misleading.
        """
        if self.reports_accepted < 3:
            return None
        return round(self.reports_confirmed / self.reports_accepted, 2)

    def recompute_level(self):
        for level, threshold in LEVEL_THRESHOLDS:
            if self.points >= threshold:
                self.level = level
                return level
        return self.level


class PointEntry(models.Model):
    """One award of points, so a total can always be explained."""

    profile = models.ForeignKey(
        ContributorProfile, on_delete=models.CASCADE, related_name="point_entries"
    )
    reason = models.CharField(_("reason"), max_length=32, choices=PointReason.choices)
    points = models.IntegerField(_("points"))
    note = models.CharField(_("note"), max_length=255, blank=True)
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="awarded_points",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("point entry")
        verbose_name_plural = _("point entries")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.points:+d} ({self.get_reason_display()})"


class Badge(models.Model):
    """A badge definition. Global, so municipalities share the same vocabulary."""

    key = models.SlugField(_("key"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=120)
    description = models.CharField(_("description"), max_length=255, blank=True)
    icon = models.CharField(
        _("icon"), max_length=16, blank=True, help_text=_("A single character or emoji.")
    )
    required_points = models.PositiveIntegerField(_("points required"), default=0)
    required_confirmed_reports = models.PositiveIntegerField(
        _("confirmed reports required"), default=0
    )
    required_inspections = models.PositiveIntegerField(_("verifications required"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("badge")
        verbose_name_plural = _("badges")
        ordering = ["required_points", "name"]

    def __str__(self):
        return self.name

    def is_earned_by(self, profile):
        return (
            profile.points >= self.required_points
            and profile.reports_confirmed >= self.required_confirmed_reports
            and profile.inspections_completed >= self.required_inspections
        )


class Award(models.Model):
    """A badge held by a contributor."""

    profile = models.ForeignKey(
        ContributorProfile, on_delete=models.CASCADE, related_name="awards"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    awarded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("award")
        verbose_name_plural = _("awards")
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "badge"], name="unique_award_per_badge")
        ]

    def __str__(self):
        return f"{self.profile}: {self.badge}"
