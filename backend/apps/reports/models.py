"""Citizen reports.

A report is an observation, not a fact. It carries what someone saw, where, and
optionally who they are — and it stays a suspicion until the administration
verifies it. Keeping reports as their own records rather than writing straight
into the property register is what makes that distinction hold.
"""

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.properties.choices import DamageType
from organizations.models import OrgQuerySet, OrganizationOwnedModel

# Report carries a field called ``property``, which is the domain word and the
# name used in related lookups. It shadows the builtin inside the class body, so
# keep a reference under another name for computed attributes.
computed = property


class ReportCategory(models.TextChoices):
    """What the reporter believes they are seeing."""

    SUSPECTED_VACANCY = "suspected_vacancy", _("Suspected vacancy")
    BUILDING_DAMAGE = "building_damage", _("Visible building damage")
    HAZARD = "hazard", _("Hazard")
    NEGLECT = "neglect", _("Neglect or accumulation of waste")
    USE_INFORMATION = "use_information", _("Information about use or condition")
    OTHER = "other", _("Other")


class ReportStatus(models.TextChoices):
    """Moderation state of the report itself.

    Separate from the workflow of the property record: a report can be accepted
    and attached to an object whose verification has not even started.
    """

    SUBMITTED = "submitted", _("Submitted")
    IN_MODERATION = "in_moderation", _("In moderation")
    ACCEPTED = "accepted", _("Accepted")
    DUPLICATE = "duplicate", _("Duplicate")
    REJECTED = "rejected", _("Rejected")
    SPAM = "spam", _("Spam")


# States a report can still be worked on from.
OPEN_REPORT_STATUSES = frozenset({ReportStatus.SUBMITTED, ReportStatus.IN_MODERATION})

# States that mean the report was set aside. Rejected and spam reports are
# subject to the retention rule, because keeping unfounded accusations about a
# building indefinitely is not defensible.
DISCARDED_REPORT_STATUSES = frozenset({ReportStatus.REJECTED, ReportStatus.SPAM})


class ReportQuerySet(OrgQuerySet):
    def open(self):
        return self.filter(status__in=OPEN_REPORT_STATUSES)

    def accepted(self):
        return self.filter(status=ReportStatus.ACCEPTED)

    def unlinked(self):
        """Accepted reports that are not attached to a record yet."""
        return self.filter(status=ReportStatus.ACCEPTED, property__isnull=True)


def report_photo_path(instance, filename):
    return f"reports/org_{instance.report.organization_id}/{instance.report_id}/{filename}"


class Report(OrganizationOwnedModel):
    """One observation submitted by a citizen."""

    objects = ReportQuerySet.as_manager()

    reference = models.CharField(_("reference"), max_length=32, blank=True)

    # --- What and where ---------------------------------------------------
    category = models.CharField(
        _("category"),
        max_length=32,
        choices=ReportCategory.choices,
        default=ReportCategory.SUSPECTED_VACANCY,
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("What did you notice? Anything you know about the building helps."),
    )
    street = models.CharField(_("street"), max_length=255, blank=True)
    house_number = models.CharField(_("house number"), max_length=32, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=16, blank=True)
    city = models.CharField(_("city"), max_length=120, blank=True)
    location = gis_models.PointField(
        _("location"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("The marker the reporter placed on the map."),
    )
    damage_types = models.JSONField(
        _("observed damage"),
        default=list,
        blank=True,
        help_text=_("Damage the reporter marked. An observation, not an assessment."),
    )

    # --- Who --------------------------------------------------------------
    # Reporting must work without an account, so the submitter is optional. When
    # someone does leave contact details, that is personal data: it is only
    # stored with consent and only visible to the administration.
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
        verbose_name=_("submitted by"),
    )
    contact_name = models.CharField(_("name"), max_length=200, blank=True)
    contact_email = models.EmailField(_("email"), blank=True)
    contact_phone = models.CharField(_("phone"), max_length=50, blank=True)
    wants_feedback = models.BooleanField(
        _("would like to hear back"),
        default=False,
        help_text=_("Only possible if contact details were provided."),
    )

    # --- Consent ----------------------------------------------------------
    # Recorded per report, with the time, because consent has to be evidenced.
    accepted_privacy_policy = models.BooleanField(_("privacy policy accepted"), default=False)
    accepted_terms = models.BooleanField(_("terms accepted"), default=False)
    consent_given_at = models.DateTimeField(_("consent given at"), null=True, blank=True)

    # --- Moderation -------------------------------------------------------
    status = models.CharField(
        _("status"), max_length=32, choices=ReportStatus.choices, default=ReportStatus.SUBMITTED
    )
    moderation_note = models.TextField(_("moderation note"), blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_reports",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    # --- Result -----------------------------------------------------------
    property = models.ForeignKey(
        "properties.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
        verbose_name=_("property record"),
    )
    district = models.ForeignKey(
        "municipalities.District",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
    )

    # --- Provenance -------------------------------------------------------
    # Kept for abuse handling only, and covered by the retention rules.
    submitted_from_ip = models.GenericIPAddressField(
        _("submitted from"), null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("report")
        verbose_name_plural = _("reports")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_report_reference_per_tenant"
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.reference or self.pk}: {self.get_category_display()}"

    def get_absolute_url(self):
        return reverse("reports:detail", kwargs={"pk": self.pk})

    @computed
    def address_line(self):
        street = " ".join(part for part in (self.street, self.house_number) if part)
        locality = " ".join(part for part in (self.postal_code, self.city) if part)
        line = ", ".join(part for part in (street, locality) if part)
        if line:
            return line
        if self.location is not None:
            return f"{self.location.y:.5f}, {self.location.x:.5f}"
        return str(_("Location unknown"))

    @computed
    def is_anonymous(self):
        return self.submitted_by_id is None

    @computed
    def has_contact_details(self):
        return bool(self.contact_email or self.contact_phone)

    @computed
    def is_open(self):
        return self.status in OPEN_REPORT_STATUSES

    @computed
    def damage_labels(self):
        """Display labels for the marked damage, ignoring unknown values."""
        known = dict(DamageType.choices)
        return [known[value] for value in self.damage_types if value in known]

    def clean(self):
        super().clean()
        if not self.location and not (self.street or self.city):
            raise ValidationError(
                _("Please either place a marker on the map or enter an address.")
            )
        if self.wants_feedback and not self.has_contact_details:
            raise ValidationError(
                {"wants_feedback": _("Feedback needs an email address or a phone number.")}
            )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.localdate().year
            pattern = f"M-{year}-"
            last = (
                Report.objects.filter(
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
                    counter = (
                        Report.objects.filter(organization_id=self.organization_id).count() + 1
                    )
            self.reference = f"{pattern}{counter:04d}"
        return super().save(*args, **kwargs)

    # --- Moderation actions ------------------------------------------------
    def moderate(self, status, actor=None, note=""):
        """Record a moderation decision."""
        self.status = ReportStatus(status)
        self.moderated_by = actor
        self.moderated_at = timezone.now()
        if note:
            self.moderation_note = note
        self.save(
            update_fields=[
                "status",
                "moderated_by",
                "moderated_at",
                "moderation_note",
                "updated_at",
            ]
        )
        return self


class ReportPhoto(models.Model):
    """A photograph attached to a report.

    Photographs from the street can show people and number plates, so they are
    internal until someone releases them deliberately.
    """

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(_("photo"), upload_to=report_photo_path)
    caption = models.CharField(_("caption"), max_length=255, blank=True)
    is_public = models.BooleanField(
        _("published"),
        default=False,
        help_text=_("Photographs stay internal until they are released explicitly."),
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("report photo")
        verbose_name_plural = _("report photos")
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.caption or f"Photo {self.pk}"
