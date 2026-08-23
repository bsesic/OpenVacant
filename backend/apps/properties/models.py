"""The property record: the professional core of the register."""

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.properties.choices import (
    ALLOWED_TRANSITIONS,
    CONFIRMED_STATUSES,
    CRITICAL_CONDITIONS,
    OPEN_CHECK_STATUSES,
    VACANCY_STATUSES,
    AssessmentSource,
    ConditionGrade,
    DamageType,
    Priority,
    PropertyType,
    RecordStatus,
    UseCategory,
    VacancyStatus,
)
from organizations.models import OrgQuerySet, OrganizationOwnedModel


class TransitionNotAllowed(ValidationError):
    """Raised when a status change is not permitted from the current status."""


class PropertyQuerySet(OrgQuerySet):
    """Queryset helpers that encode the reporting definitions in one place."""

    def public(self):
        """Only records the municipality has released for publication.

        Publication is an explicit decision on the record, never a side effect
        of its workflow status. See ADR 0009.
        """
        return self.filter(is_public=True)

    def confirmed(self):
        return self.filter(status__in=CONFIRMED_STATUSES)

    def vacant(self):
        """Confirmed vacancy. A mere suspicion is not counted."""
        return self.filter(vacancy_status__in=VACANCY_STATUSES)

    def open_checks(self):
        return self.filter(status__in=OPEN_CHECK_STATUSES)

    def critical(self):
        return self.filter(condition__in=CRITICAL_CONDITIONS)

    def in_district(self, district):
        return self.filter(district=district)


class Property(OrganizationOwnedModel):
    """One recorded object: a building, a plot or a brownfield site."""

    objects = PropertyQuerySet.as_manager()

    reference = models.CharField(
        _("reference"),
        max_length=32,
        blank=True,
        help_text=_("Register number, assigned automatically."),
    )
    district = models.ForeignKey(
        "municipalities.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="properties",
        verbose_name=_("district"),
    )

    # --- Address ----------------------------------------------------------
    street = models.CharField(_("street"), max_length=255, blank=True)
    house_number = models.CharField(_("house number"), max_length=32, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=16, blank=True)
    city = models.CharField(_("city"), max_length=120, blank=True)
    address_note = models.CharField(
        _("address note"),
        max_length=255,
        blank=True,
        help_text=_("For objects without a usable address, e.g. “behind no. 14”."),
    )
    location = gis_models.PointField(
        _("location"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("Where the object sits on the map."),
    )

    # --- Classification ---------------------------------------------------
    property_type = models.CharField(
        _("property type"),
        max_length=32,
        choices=PropertyType.choices,
        default=PropertyType.RESIDENTIAL,
    )
    last_known_use = models.CharField(
        _("last known use"),
        max_length=32,
        choices=UseCategory.choices,
        default=UseCategory.UNKNOWN,
    )

    # --- State ------------------------------------------------------------
    status = models.CharField(
        _("record status"),
        max_length=32,
        choices=RecordStatus.choices,
        default=RecordStatus.NEW,
    )
    vacancy_status = models.CharField(
        _("vacancy status"),
        max_length=32,
        choices=VacancyStatus.choices,
        default=VacancyStatus.UNKNOWN,
    )
    condition = models.CharField(
        _("condition"),
        max_length=32,
        choices=ConditionGrade.choices,
        default=ConditionGrade.UNKNOWN,
    )
    condition_source = models.CharField(
        _("condition assessed by"),
        max_length=32,
        choices=AssessmentSource.choices,
        default=AssessmentSource.UNKNOWN,
        help_text=_("The register does not replace an expert opinion."),
    )
    priority = models.CharField(
        _("priority"), max_length=16, choices=Priority.choices, default=Priority.MEDIUM
    )

    # --- Dates ------------------------------------------------------------
    recorded_on = models.DateField(_("recorded on"), default=timezone.localdate)
    last_checked_on = models.DateField(_("last checked on"), null=True, blank=True)

    # --- Descriptions -----------------------------------------------------
    # Two separate fields rather than one plus a flag: it must be impossible to
    # publish internal wording by flipping a boolean. See ADR 0009.
    public_description = models.TextField(
        _("public description"),
        blank=True,
        help_text=_("Visible to everyone wherever this object is published."),
    )
    internal_description = models.TextField(
        _("internal description"),
        blank=True,
        help_text=_("Never leaves the administration."),
    )
    sources = models.TextField(
        _("sources"),
        blank=True,
        help_text=_("Where the information came from: reports, site visits, files."),
    )

    # --- Publication ------------------------------------------------------
    is_public = models.BooleanField(
        _("published"),
        default=False,
        help_text=_("Whether this object appears on the public map and in the public API."),
    )

    # --- Optional professional data --------------------------------------
    parcels = models.ManyToManyField(
        "parcels.Parcel",
        blank=True,
        related_name="properties",
        verbose_name=_("parcels"),
        help_text=_("A building can sit on more than one parcel."),
    )
    plot_area_sqm = models.DecimalField(
        _("plot area in m²"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    usable_area_sqm = models.DecimalField(
        _("usable area in m²"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    living_area_sqm = models.DecimalField(
        _("living area in m²"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    year_built = models.PositiveSmallIntegerField(_("year built"), null=True, blank=True)
    units_total = models.PositiveIntegerField(_("units in total"), null=True, blank=True)
    units_vacant = models.PositiveIntegerField(_("vacant units"), null=True, blank=True)

    # --- Spatial context --------------------------------------------------
    # Derived from imported geo layers rather than typed in, and recomputed when
    # layers change. They are stored so that filtering and statistics stay cheap.
    is_heritage_protected = models.BooleanField(_("heritage protected"), default=False)
    in_redevelopment_area = models.BooleanField(_("in a redevelopment area"), default=False)
    in_funding_area = models.BooleanField(_("in a funding area"), default=False)
    in_development_area = models.BooleanField(_("in a development area"), default=False)
    context_updated_at = models.DateTimeField(
        _("spatial context updated at"), null=True, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_properties",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords(excluded_fields=["context_updated_at"])

    class Meta:
        verbose_name = _("property")
        verbose_name_plural = _("properties")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_property_reference_per_tenant"
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["vacancy_status"]),
            models.Index(fields=["condition"]),
            models.Index(fields=["is_public"]),
        ]

    def __str__(self):
        return f"{self.reference} · {self.address_line}" if self.reference else self.address_line

    def get_absolute_url(self):
        return reverse("properties:detail", kwargs={"pk": self.pk})

    # --- Presentation -----------------------------------------------------
    @property
    def address_line(self):
        """A single-line address, falling back to the note or the coordinates."""
        street = " ".join(part for part in (self.street, self.house_number) if part)
        locality = " ".join(part for part in (self.postal_code, self.city) if part)
        line = ", ".join(part for part in (street, locality) if part)
        if line:
            return line
        if self.address_note:
            return self.address_note
        if self.location is not None:
            return f"{self.location.y:.5f}, {self.location.x:.5f}"
        return str(_("Location unknown"))

    # --- Derived facts ----------------------------------------------------
    @property
    def is_vacant(self):
        return self.vacancy_status in VACANCY_STATUSES

    @property
    def is_confirmed(self):
        return self.status in CONFIRMED_STATUSES

    @property
    def needs_check(self):
        return self.status in OPEN_CHECK_STATUSES

    @property
    def is_critical(self):
        return self.condition in CRITICAL_CONDITIONS

    @property
    def is_expert_assessed(self):
        """Whether the recorded condition rests on more than an observation."""
        return self.condition_source in (
            AssessmentSource.STAFF_ASSESSMENT,
            AssessmentSource.EXPERT_REPORT,
        )

    def allowed_transitions(self):
        return sorted(ALLOWED_TRANSITIONS.get(self.status, set()))

    def can_transition_to(self, status):
        return status in ALLOWED_TRANSITIONS.get(self.status, set())

    # --- Validation -------------------------------------------------------
    def clean(self):
        super().clean()
        if self.district_id and self.organization_id:
            municipality = getattr(self.district, "municipality", None)
            if municipality and municipality.organization_id != self.organization_id:
                raise ValidationError(
                    {"district": _("The district must belong to the same municipality.")}
                )
        if (
            self.units_total is not None
            and self.units_vacant is not None
            and self.units_vacant > self.units_total
        ):
            raise ValidationError(
                {"units_vacant": _("There cannot be more vacant units than units in total.")}
            )

    # --- Reference numbers -------------------------------------------------
    def _build_reference(self):
        """Build a per-municipality register number such as ``RB-2026-0001``."""
        municipality = getattr(self.organization, "municipality", None)
        prefix = "OV"
        if municipality is not None:
            source = municipality.municipality_key or municipality.name
            letters = "".join(ch for ch in source.upper() if ch.isalnum())
            prefix = letters[:3] or "OV"
        year = self.recorded_on.year if self.recorded_on else timezone.localdate().year
        pattern = f"{prefix}-{year}-"
        last = (
            Property.objects.filter(
                organization_id=self.organization_id, reference__startswith=pattern
            )
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )
        counter = 1
        if last:
            try:
                counter = int(last.rsplit("-", 1)[1]) + 1
            except (IndexError, ValueError):
                counter = Property.objects.filter(
                    organization_id=self.organization_id
                ).count() + 1
        return f"{pattern}{counter:04d}"

    def save(self, *args, **kwargs):
        if not self.reference:
            # Concurrent inserts can pick the same number; the unique constraint
            # catches it and the next attempt sees the winner's row.
            for _attempt in range(5):
                self.reference = self._build_reference()
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.reference = ""
                    continue
            self.reference = self._build_reference()
        return super().save(*args, **kwargs)

    # --- Workflow ----------------------------------------------------------
    def transition_to(self, status, actor=None, reason="", note=""):
        """Move the record to ``status``, recording who did it and why.

        Every change is logged. A record never changes status implicitly, which
        is what makes the process auditable.
        """
        status = RecordStatus(status)
        if status == self.status:
            return None
        if not self.can_transition_to(status):
            raise TransitionNotAllowed(
                _("A record cannot move from “%(current)s” to “%(target)s”.")
                % {
                    "current": self.get_status_display(),
                    "target": RecordStatus(status).label,
                }
            )
        previous = self.status
        with transaction.atomic():
            self.status = status
            self.last_checked_on = timezone.localdate()
            self.save(update_fields=["status", "last_checked_on", "updated_at"])
            return StatusTransition.objects.create(
                property=self,
                from_status=previous,
                to_status=status,
                actor=actor,
                reason=reason,
                note=note,
            )

    def set_vacancy_status(self, status, actor=None, source="", note=""):
        """Record a change in occupancy and keep the vacancy history in step."""
        from apps.vacancies.models import record_vacancy_change

        status = VacancyStatus(status)
        if status == self.vacancy_status:
            return None
        self.vacancy_status = status
        self.save(update_fields=["vacancy_status", "updated_at"])
        return record_vacancy_change(self, status, actor=actor, source=source, note=note)

    def mark_damage(self, damage_type, severity=None, source=AssessmentSource.UNKNOWN, note=""):
        """Add or update a damage marker on this object."""
        damage, _created = PropertyDamage.objects.update_or_create(
            property=self,
            damage_type=damage_type,
            defaults={
                "severity": severity or PropertyDamage.Severity.PRESENT,
                "source": source,
                "note": note,
            },
        )
        return damage


class StatusTransition(models.Model):
    """An audit entry for one change of a record's workflow status."""

    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="status_transitions"
    )
    from_status = models.CharField(_("from"), max_length=32, choices=RecordStatus.choices)
    to_status = models.CharField(_("to"), max_length=32, choices=RecordStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_transitions",
    )
    reason = models.CharField(_("reason"), max_length=255, blank=True)
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("status change")
        verbose_name_plural = _("status changes")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.property_id}: {self.from_status} → {self.to_status}"


class PropertyDamage(models.Model):
    """One marked defect on an object."""

    class Severity(models.TextChoices):
        PRESENT = "present", _("Present")
        SEVERE = "severe", _("Severe")
        HAZARDOUS = "hazardous", _("Hazardous")

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="damages")
    damage_type = models.CharField(_("damage"), max_length=32, choices=DamageType.choices)
    severity = models.CharField(
        _("severity"), max_length=16, choices=Severity.choices, default=Severity.PRESENT
    )
    source = models.CharField(
        _("noted by"),
        max_length=32,
        choices=AssessmentSource.choices,
        default=AssessmentSource.UNKNOWN,
    )
    note = models.CharField(_("note"), max_length=255, blank=True)
    noted_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("damage")
        verbose_name_plural = _("damages")
        ordering = ["damage_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "damage_type"], name="unique_damage_type_per_property"
            )
        ]

    def __str__(self):
        return f"{self.get_damage_type_display()} ({self.get_severity_display()})"
