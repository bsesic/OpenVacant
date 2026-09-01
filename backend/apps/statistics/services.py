"""Computing the key figures.

Every definition the register reports on lives here, once. If "confirmed
vacancy" is counted differently on the dashboard than in the export, the numbers
stop being usable for a council decision — so both read from this module.
"""

import datetime

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.properties.choices import (
    ConditionGrade,
    PropertyType,
    RecordStatus,
    VacancyStatus,
)
from apps.properties.models import Property
from apps.reports.models import Report, ReportStatus
from apps.workflows.models import Task

# Statuses that mean a case stopped being an open vacancy problem: the object is
# in use again, was demolished, or the record was closed as unfounded.
RESOLVED_STATUSES = frozenset({RecordStatus.NOT_CONFIRMED, RecordStatus.ARCHIVED})


def _counts_by(queryset, field, labels):
    """Count rows per choice value, keeping the label and including zeroes.

    Zero rows are kept deliberately: "no severely damaged buildings" is a result,
    and dropping the row would make the table look incomplete instead.
    """
    raw = dict(
        queryset.values_list(field).annotate(total=Count("pk")).values_list(field, "total")
    )
    return [
        {"key": value, "label": str(label), "count": raw.get(value, 0)}
        for value, label in labels
    ]


def key_figures(organization):
    """The headline numbers for one municipality."""
    records = Property.objects.for_organization(organization)
    reports = Report.objects.for_organization(organization)
    tasks = Task.objects.for_organization(organization)

    vacant = records.vacant()
    return {
        "total_records": records.count(),
        "confirmed_records": records.confirmed().count(),
        "confirmed_vacancies": vacant.count(),
        "suspected_vacancies": records.filter(
            vacancy_status=VacancyStatus.SUSPECTED_VACANT
        ).count(),
        "open_checks": records.open_checks().count(),
        "critical_records": records.critical().count(),
        "heritage_vacancies": vacant.filter(is_heritage_protected=True).count(),
        "redevelopment_vacancies": vacant.filter(in_redevelopment_area=True).count(),
        "published_records": records.public().count(),
        "open_reports": reports.open().count(),
        "unlinked_reports": reports.unlinked().count(),
        "open_tasks": tasks.open().count(),
        "overdue_tasks": tasks.overdue().count(),
    }


def breakdowns(organization):
    """Vacancy broken down the ways the specification asks for."""
    records = Property.objects.for_organization(organization)
    vacant = records.vacant()

    by_district = list(
        vacant.values("district__name")
        .annotate(count=Count("pk"))
        .order_by("-count", "district__name")
    )
    return {
        "by_district": [
            {
                "label": entry["district__name"] or str(_unassigned_label()),
                "count": entry["count"],
            }
            for entry in by_district
        ],
        "by_property_type": _counts_by(vacant, "property_type", PropertyType.choices),
        "by_condition": _counts_by(vacant, "condition", ConditionGrade.choices),
        "by_status": _counts_by(records, "status", RecordStatus.choices),
    }


def _unassigned_label():
    from django.utils.translation import gettext

    return gettext("No district")


def monthly_series(organization, months=12, today=None):
    """New and resolved cases per month.

    "New" counts reports as they arrive, because that is when a case enters the
    municipality's world. "Resolved" counts records moving to not confirmed or
    archived, which is when it leaves.
    """
    today = today or timezone.localdate()
    start = (today.replace(day=1) - datetime.timedelta(days=31 * (months - 1))).replace(day=1)

    new_reports = dict(
        Report.objects.for_organization(organization)
        .filter(created_at__date__gte=start)
        .annotate(month=TruncMonth("created_at"))
        .values_list("month")
        .annotate(total=Count("pk"))
        .values_list("month", "total")
    )
    resolved = dict(
        Property.objects.for_organization(organization)
        .filter(status__in=RESOLVED_STATUSES, updated_at__date__gte=start)
        .annotate(month=TruncMonth("updated_at"))
        .values_list("month")
        .annotate(total=Count("pk"))
        .values_list("month", "total")
    )

    def _key(value):
        return (value.year, value.month) if value else None

    new_by_month = {_key(month): total for month, total in new_reports.items()}
    resolved_by_month = {_key(month): total for month, total in resolved.items()}

    series = []
    cursor = start
    while cursor <= today:
        key = (cursor.year, cursor.month)
        series.append(
            {
                "month": cursor.isoformat(),
                "label": cursor.strftime("%Y-%m"),
                "new": new_by_month.get(key, 0),
                "resolved": resolved_by_month.get(key, 0),
            }
        )
        cursor = (cursor + datetime.timedelta(days=31)).replace(day=1)
    return series


def dashboard_context(organization, months=12):
    """Everything the administration dashboard shows."""
    records = Property.objects.for_organization(organization)
    reports = Report.objects.for_organization(organization)
    tasks = Task.objects.for_organization(organization)

    return {
        "figures": key_figures(organization),
        "breakdowns": breakdowns(organization),
        "series": monthly_series(organization, months=months),
        "recent_reports": reports.filter(status=ReportStatus.SUBMITTED).select_related(
            "property"
        )[:8],
        "recent_records": records.select_related("district")[:8],
        "open_tasks": tasks.open().select_related("assignee", "property")[:8],
        "critical_records": records.critical().select_related("district")[:8],
    }


def take_snapshot(organization, on=None):
    """Store today's figures, replacing an existing snapshot for the same day."""
    from apps.statistics.models import KeyFigureSnapshot

    taken_on = on or timezone.localdate()
    figures = key_figures(organization)
    figures["breakdowns"] = breakdowns(organization)
    snapshot, _created = KeyFigureSnapshot.objects.update_or_create(
        organization=organization, taken_on=taken_on, defaults={"figures": figures}
    )
    return snapshot
