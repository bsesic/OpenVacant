"""The municipality profile and its territorial subdivisions.

A tenant (``organizations.Organization``) carries the membership machinery; the
professional and public identity of the body running the register lives here. See
ADR 0008 for why the two are separate.
"""

from django.contrib.gis.db import models as gis_models
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# Municipalities are identified by their official municipality key (in Germany
# the eight-digit Amtlicher Gemeindeschlüssel).
MUNICIPALITY_KEY_VALIDATOR = RegexValidator(
    r"^\d{5,12}$",
    _("Enter the official municipality key as digits only."),
)

HEX_COLOUR_VALIDATOR = RegexValidator(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
    _("Enter a colour as a hex value, for example #1d4ed8."),
)


class FederalState(models.TextChoices):
    """German federal states, used for jurisdiction and geodata sources."""

    BW = "BW", _("Baden-Württemberg")
    BY = "BY", _("Bavaria")
    BE = "BE", _("Berlin")
    BB = "BB", _("Brandenburg")
    HB = "HB", _("Bremen")
    HH = "HH", _("Hamburg")
    HE = "HE", _("Hesse")
    MV = "MV", _("Mecklenburg-Vorpommern")
    NI = "NI", _("Lower Saxony")
    NW = "NW", _("North Rhine-Westphalia")
    RP = "RP", _("Rhineland-Palatinate")
    SL = "SL", _("Saarland")
    SN = "SN", _("Saxony")
    ST = "ST", _("Saxony-Anhalt")
    SH = "SH", _("Schleswig-Holstein")
    TH = "TH", _("Thuringia")


class TenantKind(models.TextChoices):
    """What kind of body runs this instance.

    Federation puts a district or a state office above the municipalities; they
    reuse the same tenancy, so the kind has to be explicit.
    """

    MUNICIPALITY = "municipality", _("Municipality")
    DISTRICT_AUTHORITY = "district_authority", _("District authority")
    STATE_AUTHORITY = "state_authority", _("State authority")


class Module(models.TextChoices):
    """Optional modules a municipality can switch on or off.

    Only genuinely optional parts appear here. The property record, reporting and
    verification are the core of the register and cannot be disabled.
    """

    PUBLIC_MAP = "public_map", _("Public map")
    ANONYMOUS_REPORTS = "anonymous_reports", _("Anonymous reports")
    CITIZEN_VERIFICATION = "citizen_verification", _("Verification by citizens")
    HERITAGE = "heritage", _("Heritage protection data")
    FUNDING = "funding", _("Funding programmes")
    OWNER_PORTAL = "owner_portal", _("Owner portal")
    PARTICIPATION = "participation", _("Participation and reputation")
    FEDERATION = "federation", _("Federation with other instances")
    PUBLIC_API = "public_api", _("Public API")

    @classmethod
    def defaults(cls):
        """Modules that are enabled unless a municipality turns them off.

        The prepared future-phase modules stay off until a municipality asks for
        them; everything the MVP demonstrates is on.
        """
        return {
            cls.PUBLIC_MAP: True,
            cls.ANONYMOUS_REPORTS: True,
            cls.CITIZEN_VERIFICATION: True,
            cls.HERITAGE: True,
            cls.FUNDING: False,
            cls.OWNER_PORTAL: False,
            cls.PARTICIPATION: True,
            cls.FEDERATION: False,
            cls.PUBLIC_API: True,
        }


class Municipality(models.Model):
    """The public and professional identity of the body running the register."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="municipality",
        verbose_name=_("tenant"),
    )
    kind = models.CharField(
        _("kind"),
        max_length=32,
        choices=TenantKind.choices,
        default=TenantKind.MUNICIPALITY,
    )

    # --- Identity ---------------------------------------------------------
    name = models.CharField(_("name"), max_length=200)
    official_name = models.CharField(
        _("official name"),
        max_length=255,
        blank=True,
        help_text=_("Full legal name, if it differs from the everyday name."),
    )
    municipality_key = models.CharField(
        _("municipality key"),
        max_length=12,
        blank=True,
        validators=[MUNICIPALITY_KEY_VALIDATOR],
        help_text=_("Official municipality key (AGS), digits only."),
    )
    state = models.CharField(_("federal state"), max_length=2, choices=FederalState.choices)
    district_name = models.CharField(
        _("district"),
        max_length=200,
        blank=True,
        help_text=_("The rural or urban district this municipality belongs to."),
    )

    # --- Contact ----------------------------------------------------------
    contact_email = models.EmailField(_("contact email"), blank=True)
    contact_phone = models.CharField(_("contact phone"), max_length=50, blank=True)
    postal_address = models.TextField(_("postal address"), blank=True)
    website = models.URLField(_("website"), blank=True)

    # --- Geography --------------------------------------------------------
    # WGS 84 throughout: map frontends, geocoders and imported GeoJSON all speak
    # it, and the register never needs metric precision on the geometry itself.
    centre = gis_models.PointField(
        _("map centre"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("Where the map opens. Falls back to the instance default."),
    )
    boundary = gis_models.MultiPolygonField(
        _("boundary"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("Territory of this municipality, used to route reports to it."),
    )
    default_zoom = models.PositiveSmallIntegerField(_("default zoom"), null=True, blank=True)

    # --- White label ------------------------------------------------------
    domain = models.CharField(
        _("domain"),
        max_length=255,
        blank=True,
        help_text=_("Host this instance answers on, used to pick the branding."),
    )
    logo = models.ImageField(_("logo"), upload_to="branding/", blank=True)
    coat_of_arms = models.ImageField(_("coat of arms"), upload_to="branding/", blank=True)
    primary_colour = models.CharField(
        _("primary colour"),
        max_length=7,
        blank=True,
        validators=[HEX_COLOUR_VALIDATOR],
    )
    accent_colour = models.CharField(
        _("accent colour"),
        max_length=7,
        blank=True,
        validators=[HEX_COLOUR_VALIDATOR],
    )
    font_family = models.CharField(
        _("font family"),
        max_length=255,
        blank=True,
        help_text=_("CSS font stack, for example 'Inter', system-ui, sans-serif."),
    )

    # --- Legal texts ------------------------------------------------------
    # Kept per municipality because each one is the data controller for its own
    # instance and publishes its own imprint and privacy notice.
    imprint = models.TextField(_("imprint"), blank=True)
    privacy_notice = models.TextField(_("privacy notice"), blank=True)
    terms = models.TextField(_("terms of use"), blank=True)

    # --- Public presentation ---------------------------------------------
    public_intro = models.TextField(
        _("public introduction"),
        blank=True,
        help_text=_("Shown to citizens on the landing page of the reporting portal."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("municipality")
        verbose_name_plural = _("municipalities")
        ordering = ["name"]
        indexes = [models.Index(fields=["domain"])]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("municipalities:detail", kwargs={"pk": self.pk})

    # --- Modules ----------------------------------------------------------
    def module_enabled(self, module):
        """Whether ``module`` is active, falling back to the platform default."""
        activation = self.module_activations.filter(module=module).first()
        if activation is not None:
            return activation.enabled
        return Module.defaults().get(module, False)

    def enabled_modules(self):
        """The set of active module keys, for templates and API responses."""
        overrides = {a.module: a.enabled for a in self.module_activations.all()}
        return {
            module
            for module, default in Module.defaults().items()
            if overrides.get(module, default)
        }

    def set_module(self, module, enabled):
        activation, _created = ModuleActivation.objects.update_or_create(
            municipality=self, module=module, defaults={"enabled": enabled}
        )
        return activation

    # --- Geography --------------------------------------------------------
    def contains(self, point):
        """Whether ``point`` lies inside this municipality's boundary.

        With no boundary imported yet, nothing can be attributed to it, so this
        is False rather than True — guessing would silently misroute reports.
        """
        if self.boundary is None or point is None:
            return False
        return self.boundary.contains(point)

    def district_for_point(self, point):
        """The district containing ``point``, or None."""
        if point is None:
            return None
        return self.districts.filter(boundary__contains=point).first()


class ModuleActivation(models.Model):
    """A municipality's explicit decision about one optional module."""

    municipality = models.ForeignKey(
        Municipality, on_delete=models.CASCADE, related_name="module_activations"
    )
    module = models.CharField(_("module"), max_length=64, choices=Module.choices)
    enabled = models.BooleanField(_("enabled"), default=True)
    changed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("module activation")
        verbose_name_plural = _("module activations")
        constraints = [
            models.UniqueConstraint(
                fields=["municipality", "module"], name="unique_module_per_municipality"
            )
        ]
        ordering = ["municipality", "module"]

    def __str__(self):
        state = _("enabled") if self.enabled else _("disabled")
        return f"{self.municipality}: {self.get_module_display()} ({state})"


class DistrictKind(models.TextChoices):
    BOROUGH = "borough", _("Borough")
    LOCALITY = "locality", _("Locality")
    QUARTER = "quarter", _("Quarter")


class District(models.Model):
    """A territorial subdivision: the unit statistics are reported per."""

    municipality = models.ForeignKey(
        Municipality, on_delete=models.CASCADE, related_name="districts"
    )
    name = models.CharField(_("name"), max_length=200)
    kind = models.CharField(
        _("kind"), max_length=20, choices=DistrictKind.choices, default=DistrictKind.LOCALITY
    )
    code = models.CharField(
        _("code"),
        max_length=32,
        blank=True,
        help_text=_("Official or internal key for this district."),
    )
    boundary = gis_models.MultiPolygonField(_("boundary"), srid=4326, null=True, blank=True)
    centre = gis_models.PointField(_("centre"), srid=4326, null=True, blank=True)
    note = models.TextField(_("note"), blank=True)

    class Meta:
        verbose_name = _("district")
        verbose_name_plural = _("districts")
        ordering = ["municipality", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipality", "name"], name="unique_district_name_per_municipality"
            )
        ]

    def __str__(self):
        return self.name
