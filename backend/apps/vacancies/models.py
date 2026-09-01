"""Vacancy history.

The current occupancy of an object lives on the property record; this app keeps
the timeline behind it. Without periods, a building that stood empty for six
years and was then let looks identical to one that was never empty, and the key
figure "how long has this been vacant" cannot be produced at all.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.properties.choices import VACANCY_STATUSES, VacancyStatus
from organizations.models import OrganizationOwnedModel

# These models carry a field called ``property``, which is the domain word and
# the name used in related lookups. It shadows the builtin inside the class
# body, so keep a reference under another name for computed attributes.
computed = property


class VacancyPeriod(OrganizationOwnedModel):
    """A stretch of time during which an object held one occupancy status.

    An open period (``ended_on`` is null) is the current one.
    """

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="vacancy_periods",
        verbose_name=_("property"),
    )
    status = models.CharField(
        _("status"), max_length=32, choices=VacancyStatus.choices
    )
    started_on = models.DateField(_("from"), default=timezone.localdate)
    ended_on = models.DateField(_("until"), null=True, blank=True)
    source = models.CharField(
        _("source"),
        max_length=255,
        blank=True,
        help_text=_("How this was established: site visit, report, owner information."),
    )
    note = models.TextField(_("note"), blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_vacancy_periods",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("vacancy period")
        verbose_name_plural = _("vacancy periods")
        ordering = ["-started_on", "-created_at"]
        indexes = [
            models.Index(fields=["property", "ended_on"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        until = self.ended_on.isoformat() if self.ended_on else _("ongoing")
        return f"{self.get_status_display()}: {self.started_on} – {until}"

    @computed
    def is_open(self):
        return self.ended_on is None

    @computed
    def counts_as_vacancy(self):
        """Whether this period is vacancy for reporting purposes."""
        return self.status in VACANCY_STATUSES

    def duration_days(self, until=None):
        """Length of the period in days, measured to today while still open."""
        end = self.ended_on or until or timezone.localdate()
        return max((end - self.started_on).days, 0)


def record_vacancy_change(property_obj, status, actor=None, source="", note="", on=None):
    """Close the open period and open a new one for ``status``.

    Called from ``Property.set_vacancy_status`` so that the timeline cannot drift
    away from the current status stored on the record.
    """
    today = on or timezone.localdate()
    open_period = property_obj.vacancy_periods.filter(ended_on__isnull=True).first()
    if open_period is not None:
        # A period that would end before it began means the change was recorded
        # with an earlier date than the previous one; keep it a zero-length day
        # rather than writing an inverted interval.
        open_period.ended_on = max(today, open_period.started_on)
        open_period.save(update_fields=["ended_on"])
    return VacancyPeriod.objects.create(
        organization=property_obj.organization,
        property=property_obj,
        status=status,
        started_on=today,
        source=source,
        note=note,
        recorded_by=actor,
    )


def vacancy_duration_days(property_obj):
    """Days the object has continuously been vacant, or None if it is not.

    Only the current open period counts: this answers "how long has this been
    standing empty", not "how long in total over the years".
    """
    period = property_obj.vacancy_periods.filter(ended_on__isnull=True).first()
    if period is None or not period.counts_as_vacancy:
        return None
    return period.duration_days()
