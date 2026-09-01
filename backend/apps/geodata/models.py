"""External geodata layers and the spatial context they give a property.

A vacant building inside a redevelopment area, a heritage ensemble or a funding
programme is a different case from the same building outside one. The
municipality already holds that knowledge as geodata; this app imports it and
answers, per object, which layers it falls inside.
"""

from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

# SpatialContext carries a field called ``property``, which shadows the builtin
# inside the class body; keep a reference for computed attributes.
computed = property


class LayerCategory(models.TextChoices):
    """What a layer means, so context flags can be derived from it.

    The category is what makes an imported layer useful: without it the register
    would hold polygons it cannot interpret.
    """

    HERITAGE = "heritage", _("Heritage protection")
    REDEVELOPMENT = "redevelopment", _("Redevelopment area")
    FUNDING = "funding", _("Funding area")
    URBAN_RESTRUCTURING = "urban_restructuring", _("Urban restructuring area")
    DEVELOPMENT = "development", _("Development area")
    QUARTER = "quarter", _("Quarter of particular significance")
    LAND_VALUE = "land_value", _("Standard land value zone")
    OTHER = "other", _("Other")


# Which context flag on a property each category sets. Categories that are
# useful to see on the map but do not drive a flag are simply absent.
CATEGORY_TO_FLAG = {
    LayerCategory.HERITAGE: "is_heritage_protected",
    LayerCategory.REDEVELOPMENT: "in_redevelopment_area",
    LayerCategory.FUNDING: "in_funding_area",
    LayerCategory.DEVELOPMENT: "in_development_area",
}

CONTEXT_FLAGS = tuple(dict.fromkeys(CATEGORY_TO_FLAG.values()))


class GeoLayer(OrganizationOwnedModel):
    """One imported geodata layer belonging to a municipality."""

    objects = OrgQuerySet.as_manager()

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(
        _("key"),
        max_length=255,
        help_text=_("Stable key, so a repeated import replaces the same layer."),
    )
    category = models.CharField(
        _("category"), max_length=32, choices=LayerCategory.choices, default=LayerCategory.OTHER
    )
    description = models.TextField(_("description"), blank=True)
    source = models.CharField(
        _("source"),
        max_length=255,
        blank=True,
        help_text=_("Where the data came from, e.g. the state geodata portal."),
    )
    source_url = models.URLField(_("source URL"), blank=True)
    licence = models.CharField(_("licence"), max_length=255, blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive layers are kept but ignored when deriving context."),
    )
    is_public = models.BooleanField(
        _("public"),
        default=False,
        help_text=_("Whether this layer may be shown on the public map."),
    )
    imported_at = models.DateTimeField(_("imported at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("geodata layer")
        verbose_name_plural = _("geodata layers")
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="unique_layer_slug_per_tenant"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def flag(self):
        """The property flag this layer drives, if any."""
        return CATEGORY_TO_FLAG.get(self.category)

    @property
    def feature_count(self):
        return self.features.count()


class GeoFeature(models.Model):
    """A single geometry inside a layer."""

    layer = models.ForeignKey(GeoLayer, on_delete=models.CASCADE, related_name="features")
    name = models.CharField(_("name"), max_length=255, blank=True)
    external_id = models.CharField(
        _("external id"),
        max_length=255,
        blank=True,
        help_text=_("Identifier in the source system, for repeatable imports."),
    )
    # A GeometryField rather than a polygon field: official layers mix polygons,
    # lines and points, and refusing the mixed ones would mean refusing the layer.
    geometry = gis_models.GeometryField(_("geometry"), srid=4326)
    attributes = models.JSONField(_("attributes"), default=dict, blank=True)

    class Meta:
        verbose_name = _("geodata feature")
        verbose_name_plural = _("geodata features")
        ordering = ["layer", "name"]
        indexes = [models.Index(fields=["external_id"])]

    def __str__(self):
        return self.name or f"{self.layer} #{self.pk}"


class SpatialContext(models.Model):
    """A recorded hit: this property lies inside this feature.

    Kept as rows rather than only as flags so the register can say *why* an
    object counts as heritage-protected, and so a re-import can show what
    changed.
    """

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="spatial_contexts",
        verbose_name=_("property record"),
    )
    feature = models.ForeignKey(
        GeoFeature, on_delete=models.CASCADE, related_name="spatial_contexts"
    )
    matched_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("spatial context")
        verbose_name_plural = _("spatial contexts")
        ordering = ["feature__layer__category"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "feature"], name="unique_context_per_property_feature"
            )
        ]

    def __str__(self):
        return f"{self.property_id} in {self.feature}"

    @computed
    def category(self):
        return self.feature.layer.category
