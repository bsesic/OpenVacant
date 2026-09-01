"""Controlled vocabularies for the property record.

These are deliberately fixed choices rather than free text: statistics per
property type, condition and status are one of the deliverables, and they are
only comparable if everybody records the same categories.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class PropertyType(models.TextChoices):
    RESIDENTIAL = "residential", _("Residential building")
    MIXED_USE = "mixed_use", _("Mixed-use building")
    COMMERCIAL = "commercial", _("Commercial building")
    RETAIL = "retail", _("Retail premises")
    OFFICE = "office", _("Office building")
    INDUSTRIAL = "industrial", _("Industrial or workshop building")
    AGRICULTURAL = "agricultural", _("Agricultural building")
    PUBLIC = "public", _("Public building")
    RELIGIOUS = "religious", _("Religious building")
    OUTBUILDING = "outbuilding", _("Outbuilding or garage")
    BROWNFIELD = "brownfield", _("Brownfield site")
    BUILDING_GAP = "building_gap", _("Building gap")
    UNDEVELOPED = "undeveloped", _("Undeveloped plot")
    OTHER = "other", _("Other")


class UseCategory(models.TextChoices):
    """The last known use, which is often all that is knowable."""

    HOUSING = "housing", _("Housing")
    RETAIL = "retail", _("Retail")
    HOSPITALITY = "hospitality", _("Hospitality")
    OFFICE = "office", _("Office")
    CRAFT = "craft", _("Craft or workshop")
    STORAGE = "storage", _("Storage")
    PRODUCTION = "production", _("Production")
    PUBLIC = "public", _("Public use")
    CULTURAL = "cultural", _("Cultural use")
    AGRICULTURE = "agriculture", _("Agriculture")
    NEVER_USED = "never_used", _("Never used")
    UNKNOWN = "unknown", _("Unknown")


class VacancyStatus(models.TextChoices):
    """What the register currently believes about occupancy.

    Kept separate from the workflow status: an object can be confirmed as a
    record while its occupancy is still unclear, and occupancy changes over the
    years without the record restarting its workflow.
    """

    UNKNOWN = "unknown", _("Unknown")
    SUSPECTED_VACANT = "suspected_vacant", _("Suspected vacant")
    VACANT = "vacant", _("Vacant")
    PARTIALLY_VACANT = "partially_vacant", _("Partially vacant")
    IN_USE = "in_use", _("In use")
    UNDER_RENOVATION = "under_renovation", _("Under renovation")
    DEMOLISHED = "demolished", _("Demolished")


# Statuses that count as vacancy in the key figures. "Suspected" deliberately
# does not: an unverified suspicion must never inflate the reported numbers.
VACANCY_STATUSES = frozenset(
    {VacancyStatus.VACANT, VacancyStatus.PARTIALLY_VACANT}
)


class RecordStatus(models.TextChoices):
    """The verification workflow of the record itself.

    Mirrors the process in the specification: a citizen report is a suspicion
    that has to be checked before it becomes a confirmed object.
    """

    NEW = "new", _("New")
    PRE_CHECK = "pre_check", _("Preliminary check")
    ON_SITE_CHECK = "on_site_check", _("On-site check")
    CONFIRMED = "confirmed", _("Confirmed")
    NOT_CONFIRMED = "not_confirmed", _("Not confirmed")
    UNCLEAR = "unclear", _("Unclear")
    RESEARCH = "research", _("Further research")
    MEASURES = "measures", _("Measures under way")
    MONITORING = "monitoring", _("Monitoring")
    ARCHIVED = "archived", _("Archived")


# Allowed moves through the workflow. Anything not listed here is rejected, so
# a record cannot jump from a suspicion straight to a confirmed vacancy.
ALLOWED_TRANSITIONS = {
    RecordStatus.NEW: {RecordStatus.PRE_CHECK, RecordStatus.ARCHIVED},
    RecordStatus.PRE_CHECK: {
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.NOT_CONFIRMED,
        RecordStatus.UNCLEAR,
        RecordStatus.ARCHIVED,
    },
    RecordStatus.ON_SITE_CHECK: {
        RecordStatus.CONFIRMED,
        RecordStatus.NOT_CONFIRMED,
        RecordStatus.UNCLEAR,
    },
    RecordStatus.CONFIRMED: {
        RecordStatus.RESEARCH,
        RecordStatus.MEASURES,
        RecordStatus.MONITORING,
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.ARCHIVED,
    },
    RecordStatus.NOT_CONFIRMED: {RecordStatus.MONITORING, RecordStatus.ARCHIVED},
    RecordStatus.UNCLEAR: {
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.RESEARCH,
        RecordStatus.MONITORING,
        RecordStatus.ARCHIVED,
    },
    RecordStatus.RESEARCH: {
        RecordStatus.MEASURES,
        RecordStatus.MONITORING,
        RecordStatus.CONFIRMED,
        RecordStatus.ARCHIVED,
    },
    RecordStatus.MEASURES: {
        RecordStatus.MONITORING,
        RecordStatus.CONFIRMED,
        RecordStatus.ARCHIVED,
    },
    RecordStatus.MONITORING: {
        RecordStatus.ON_SITE_CHECK,
        RecordStatus.RESEARCH,
        RecordStatus.CONFIRMED,
        RecordStatus.ARCHIVED,
    },
    # Archived is terminal; reopening happens by an explicit decision, recorded
    # as a move back to monitoring.
    RecordStatus.ARCHIVED: {RecordStatus.MONITORING},
}

# Statuses whose objects are established enough to count as part of the register.
CONFIRMED_STATUSES = frozenset(
    {
        RecordStatus.CONFIRMED,
        RecordStatus.RESEARCH,
        RecordStatus.MEASURES,
        RecordStatus.MONITORING,
    }
)

# Statuses that represent work still owed to the object.
OPEN_CHECK_STATUSES = frozenset(
    {RecordStatus.NEW, RecordStatus.PRE_CHECK, RecordStatus.ON_SITE_CHECK, RecordStatus.UNCLEAR}
)


class ConditionGrade(models.TextChoices):
    """Standardised condition categories from the specification."""

    GOOD = "good", _("Good condition")
    MINOR_REPAIR = "minor_repair", _("Minor renovation needed")
    MAJOR_REPAIR = "major_repair", _("Significant renovation needed")
    SEVERELY_DAMAGED = "severely_damaged", _("Severely damaged")
    DANGEROUS = "dangerous", _("Acutely dangerous")
    COLLAPSE_RISK = "collapse_risk", _("Possible risk of collapse")
    UNKNOWN = "unknown", _("Not assessed")


# Conditions that make an object urgent for the regulatory office.
CRITICAL_CONDITIONS = frozenset(
    {ConditionGrade.DANGEROUS, ConditionGrade.COLLAPSE_RISK}
)


class AssessmentSource(models.TextChoices):
    """Who judged the condition.

    The register does not replace an expert opinion. Recording the source keeps
    a citizen's observation from being read as a structural assessment.
    """

    CITIZEN_OBSERVATION = "citizen_observation", _("Citizen observation")
    STAFF_ASSESSMENT = "staff_assessment", _("Assessment by the administration")
    EXPERT_REPORT = "expert_report", _("Expert report")
    UNKNOWN = "unknown", _("Unknown")


class DamageType(models.TextChoices):
    """Individual defects that can be marked on an object."""

    ROOF = "roof", _("Roof")
    FACADE = "facade", _("Facade")
    WINDOWS = "windows", _("Windows or doors")
    MOISTURE = "moisture", _("Moisture or mould")
    VEGETATION = "vegetation", _("Vegetation growth")
    FALLING_PARTS = "falling_parts", _("Falling building parts")
    STRUCTURE = "structure", _("Load-bearing structure")
    UTILITIES = "utilities", _("Building services")
    VANDALISM = "vandalism", _("Vandalism")
    WASTE = "waste", _("Waste or accumulation")
    OTHER = "other", _("Other")


class Priority(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")
