"""Cadastral parcels.

Parcels come from the official cadastre (in Germany ALKIS) where a municipality
can access it, and are otherwise recorded by hand. They are kept separate from
properties because one building can sit on several parcels, and a parcel can
outlive the building on it.
"""

from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from organizations.models import OrganizationOwnedModel


class ParcelSource(models.TextChoices):
    MANUAL = "manual", _("Recorded manually")
    CADASTRE = "cadastre", _("Official cadastre")
    IMPORT = "import", _("Geodata import")


class Parcel(OrganizationOwnedModel):
    """A single cadastral parcel."""

    cadastral_district = models.CharField(
        _("cadastral district"),
        max_length=120,
        blank=True,
        help_text=_("Gemarkung, as used by the cadastre."),
    )
    field_number = models.CharField(
        _("field number"), max_length=32, blank=True, help_text=_("Flur.")
    )
    parcel_number = models.CharField(
        _("parcel number"), max_length=64, help_text=_("Flurstücksnummer.")
    )
    geometry = gis_models.MultiPolygonField(_("geometry"), srid=4326, null=True, blank=True)
    area_sqm = models.DecimalField(
        _("area in m²"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    source = models.CharField(
        _("source"), max_length=20, choices=ParcelSource.choices, default=ParcelSource.MANUAL
    )
    source_reference = models.CharField(
        _("source reference"),
        max_length=255,
        blank=True,
        help_text=_("Identifier in the originating system, for repeatable imports."),
    )
    imported_at = models.DateTimeField(_("imported at"), null=True, blank=True)
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("parcel")
        verbose_name_plural = _("parcels")
        ordering = ["cadastral_district", "field_number", "parcel_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "cadastral_district", "field_number", "parcel_number"],
                name="unique_parcel_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["parcel_number"])]

    def __str__(self):
        parts = [p for p in (self.cadastral_district, self.field_number) if p]
        prefix = " ".join(parts)
        return f"{prefix} {self.parcel_number}".strip()

    @property
    def label(self):
        """Human-readable designation used in listings and exports."""
        return str(self)
