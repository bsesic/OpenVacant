"""Heritage protection.

Whether an object is a listed monument changes almost everything about it: who
has to be consulted, what may be done to it, and which funding applies. The
register therefore records both the monument itself and the act of checking —
because "we do not know yet" and "we checked, it is not listed" are different
answers, and only the second one can be relied on.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class ProtectionScope(models.TextChoices):
    SINGLE = "single", _("Individual monument")
    ENSEMBLE = "ensemble", _("Part of an ensemble")
    AREA = "area", _("Within a protected area")
    GROUND = "ground", _("Archaeological monument")
    GARDEN = "garden", _("Historic garden")


class MonumentRecord(OrganizationOwnedModel):
    """A monument as the heritage register describes it."""

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="monument_records",
        verbose_name=_("property record"),
    )
    designation = models.CharField(_("designation"), max_length=255)
    monument_id = models.CharField(
        _("monument number"),
        max_length=64,
        blank=True,
        help_text=_("Number in the official list of monuments."),
    )
    scope = models.CharField(
        _("scope"), max_length=20, choices=ProtectionScope.choices, default=ProtectionScope.SINGLE
    )
    authority = models.CharField(
        _("responsible authority"),
        max_length=255,
        blank=True,
        help_text=_("Lower heritage authority or state office."),
    )
    listed_on = models.DateField(_("listed on"), null=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    source = models.CharField(_("source"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("monument")
        verbose_name_plural = _("monuments")
        ordering = ["designation"]
        indexes = [models.Index(fields=["monument_id"])]

    def __str__(self):
        if self.monument_id:
            return f"{self.designation} ({self.monument_id})"
        return self.designation


class CheckResult(models.TextChoices):
    PROTECTED = "protected", _("Listed")
    NOT_PROTECTED = "not_protected", _("Not listed")
    UNCLEAR = "unclear", _("Unclear")


class HeritageCheck(OrganizationOwnedModel):
    """One recorded check of an object's heritage status."""

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="heritage_checks",
        verbose_name=_("property record"),
    )
    result = models.CharField(_("result"), max_length=20, choices=CheckResult.choices)
    checked_on = models.DateField(_("checked on"), default=timezone.localdate)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="heritage_checks",
    )
    monument = models.ForeignKey(
        MonumentRecord,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checks",
        verbose_name=_("monument"),
    )
    authority_reference = models.CharField(
        _("authority reference"),
        max_length=255,
        blank=True,
        help_text=_("File reference of the enquiry, so the answer is traceable."),
    )
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("heritage check")
        verbose_name_plural = _("heritage checks")
        ordering = ["-checked_on", "-created_at"]

    def __str__(self):
        return f"{self.checked_on}: {self.get_result_display()}"

    @computed
    def is_conclusive(self):
        """Whether this check settles the question.

        An unclear result is recorded but must not be mistaken for an answer.
        """
        return self.result in (CheckResult.PROTECTED, CheckResult.NOT_PROTECTED)

    def apply_to_property(self):
        """Write a conclusive result onto the record.

        A geodata layer can also set the heritage flag; an explicit check
        outranks it, because somebody actually asked the authority.
        """
        if not self.is_conclusive:
            return False
        record = self.property
        protected = self.result == CheckResult.PROTECTED
        if record.is_heritage_protected != protected:
            record.is_heritage_protected = protected
            record.save(update_fields=["is_heritage_protected", "updated_at"])
            return True
        return False
