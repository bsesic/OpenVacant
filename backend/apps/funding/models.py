"""Funding programmes.

Prepared for phase 2, inactive by default. Whether an object sits in a funding
area is already answered by the geodata module; this is about the programmes
themselves and how far a particular object has got with one.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class ProgrammeLevel(models.TextChoices):
    MUNICIPAL = "municipal", _("Municipal")
    DISTRICT = "district", _("District")
    STATE = "state", _("State")
    FEDERAL = "federal", _("Federal")
    EUROPEAN = "european", _("European")


class FundingProgramme(OrganizationOwnedModel):
    """A programme an object might draw on."""

    objects = OrgQuerySet.as_manager()

    name = models.CharField(_("name"), max_length=255)
    provider = models.CharField(_("provider"), max_length=255, blank=True)
    level = models.CharField(
        _("level"),
        max_length=20,
        choices=ProgrammeLevel.choices,
        default=ProgrammeLevel.MUNICIPAL,
    )
    description = models.TextField(_("description"), blank=True)
    url = models.URLField(_("information"), blank=True)
    # Which imported geo layers a programme depends on. Kept as layer keys rather
    # than foreign keys so a programme survives a layer being re-imported.
    required_layer_slugs = models.JSONField(
        _("required geodata layers"),
        default=list,
        blank=True,
        help_text=_("Layer keys an object has to fall inside to be eligible."),
    )
    starts_on = models.DateField(_("starts on"), null=True, blank=True)
    ends_on = models.DateField(_("ends on"), null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("funding programme")
        verbose_name_plural = _("funding programmes")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @computed
    def is_open(self):
        """Whether the programme can be applied to today."""
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.starts_on and self.starts_on > today:
            return False
        if self.ends_on and self.ends_on < today:
            return False
        return True


class ApplicationStatus(models.TextChoices):
    POSSIBLE = "possible", _("Possibly eligible")
    CHECKED = "checked", _("Eligibility checked")
    PREPARED = "prepared", _("Application prepared")
    SUBMITTED = "submitted", _("Application submitted")
    GRANTED = "granted", _("Granted")
    REJECTED = "rejected", _("Rejected")
    NOT_ELIGIBLE = "not_eligible", _("Not eligible")


class PropertyFunding(OrganizationOwnedModel):
    """How far one object has got with one programme."""

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="fundings",
        verbose_name=_("property record"),
    )
    programme = models.ForeignKey(
        FundingProgramme, on_delete=models.CASCADE, related_name="properties"
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.POSSIBLE,
    )
    amount = models.DecimalField(
        _("amount"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    reference = models.CharField(_("file reference"), max_length=120, blank=True)
    note = models.TextField(_("internal note"), blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_fundings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("property funding")
        verbose_name_plural = _("property fundings")
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "programme"], name="unique_funding_per_property_programme"
            )
        ]

    def __str__(self):
        return f"{self.programme}: {self.get_status_display()}"
