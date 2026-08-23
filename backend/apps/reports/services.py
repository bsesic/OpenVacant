"""Turning reports into property records."""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.properties.choices import (
    AssessmentSource,
    PropertyType,
    RecordStatus,
    VacancyStatus,
)
from apps.participation.services import record_report_accepted
from apps.properties.models import Property
from apps.reports.models import ReportCategory, ReportStatus

# Which occupancy a report's category implies. Only ever a suspicion: the
# occupancy is not treated as established until someone verifies it.
CATEGORY_TO_VACANCY = {
    ReportCategory.SUSPECTED_VACANCY: VacancyStatus.SUSPECTED_VACANT,
}


def _describe_origin(report):
    """A source line naming where the record's information came from."""
    who = _("registered user") if not report.is_anonymous else _("anonymous")
    return _("Citizen report %(reference)s (%(who)s), %(date)s") % {
        "reference": report.reference,
        "who": who,
        "date": report.created_at.date().isoformat(),
    }


@transaction.atomic
def create_property_from_report(report, actor=None, property_type=None):
    """Create a property record from ``report`` and link the two.

    The reporter's own words go into the internal description, never into the
    public one. Free text written by a member of the public can name residents,
    owners or neighbours, so publishing it automatically would leak personal
    data the municipality never reviewed.
    """
    municipality = getattr(report.organization, "municipality", None)
    district = report.district
    if district is None and municipality is not None and report.location is not None:
        district = municipality.district_for_point(report.location)

    record = Property(
        organization=report.organization,
        district=district,
        street=report.street,
        house_number=report.house_number,
        postal_code=report.postal_code,
        city=report.city,
        location=report.location,
        property_type=property_type or PropertyType.RESIDENTIAL,
        vacancy_status=CATEGORY_TO_VACANCY.get(report.category, VacancyStatus.UNKNOWN),
        condition_source=AssessmentSource.CITIZEN_OBSERVATION,
        internal_description=report.description,
        sources=_describe_origin(report),
        created_by=actor,
    )
    record.save()

    # Damage the reporter marked is recorded as an observation, which keeps it
    # distinguishable from a structural assessment.
    for damage_type in report.damage_types or []:
        record.mark_damage(damage_type, source=AssessmentSource.CITIZEN_OBSERVATION)

    attach_report_to_property(report, record, actor=actor)
    return record


@transaction.atomic
def attach_report_to_property(report, record, actor=None):
    """Attach ``report`` to an existing record and accept it.

    Used both for a fresh record and when a report turns out to concern an
    object the register already knows.
    """
    report.property = record
    report.status = ReportStatus.ACCEPTED
    report.moderated_by = actor
    report.moderated_at = timezone.now()
    report.save(
        update_fields=[
            "property",
            "status",
            "moderated_by",
            "moderated_at",
            "updated_at",
        ]
    )
    record_report_accepted(report, actor=actor)

    origin = _describe_origin(report)
    if origin not in (record.sources or ""):
        record.sources = f"{record.sources}\n{origin}".strip()
        record.save(update_fields=["sources", "updated_at"])
    return report


def start_verification(record, actor=None, reason=""):
    """Move a freshly created record into the preliminary check.

    Reports arrive as suspicions; this is the first step of the process that
    turns one into a confirmed object.
    """
    if record.status == RecordStatus.NEW:
        return record.transition_to(RecordStatus.PRE_CHECK, actor=actor, reason=reason)
    return None
