"""Persisted key figures.

The current numbers can always be counted from the records, but the numbers as
they stood last quarter cannot: a record that was confirmed in March and
demolished in July leaves no trace of what March looked like. Snapshots are what
make a time series defensible, which is the point of the statistics for council
decisions and funding applications.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel


class KeyFigureSnapshot(OrganizationOwnedModel):
    """The key figures of one municipality on one day."""

    objects = OrgQuerySet.as_manager()

    taken_on = models.DateField(_("taken on"), default=timezone.localdate)
    figures = models.JSONField(_("figures"), default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("key figure snapshot")
        verbose_name_plural = _("key figure snapshots")
        ordering = ["-taken_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "taken_on"], name="unique_snapshot_per_day"
            )
        ]

    def __str__(self):
        return f"{self.taken_on}: {self.figures.get('total_records', 0)} records"

    @property
    def total_records(self):
        return self.figures.get("total_records", 0)

    @property
    def confirmed_vacancies(self):
        return self.figures.get("confirmed_vacancies", 0)
