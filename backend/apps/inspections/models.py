"""On-site verification.

A report is a suspicion. This app records what someone actually established, by
whom, and lets that drive the record's status — which is the step that turns
scattered observations into a defensible register.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.properties.choices import (
    AssessmentSource,
    ConditionGrade,
    DamageType,
    RecordStatus,
    VacancyStatus,
)
from organizations.models import OrgQuerySet, OrganizationOwnedModel, Role

# Inspection carries a field called ``property``, which shadows the builtin
# inside the class body; keep a reference for computed attributes.
computed = property


class InspectionKind(models.TextChoices):
    DESK_CHECK = "desk_check", _("Preliminary check from the file")
    ON_SITE = "on_site", _("On-site inspection")
    FOLLOW_UP = "follow_up", _("Follow-up inspection")


class InspectionResult(models.TextChoices):
    CONFIRMED = "confirmed", _("Confirmed")
    NOT_CONFIRMED = "not_confirmed", _("Not confirmed")
    UNCLEAR = "unclear", _("Unclear")


# Which record status an inspection result leads to. Only a member of the
# administration can push a record all the way to confirmed; see
# ``Inspection.confirms_the_record``.
RESULT_TO_STATUS = {
    InspectionResult.CONFIRMED: RecordStatus.CONFIRMED,
    InspectionResult.NOT_CONFIRMED: RecordStatus.NOT_CONFIRMED,
    InspectionResult.UNCLEAR: RecordStatus.UNCLEAR,
}


def inspection_photo_path(instance, filename):
    return (
        f"inspections/org_{instance.inspection.organization_id}/"
        f"{instance.inspection_id}/{filename}"
    )


class InspectionQuerySet(OrgQuerySet):
    def on_site(self):
        return self.filter(kind=InspectionKind.ON_SITE)

    def confirming(self):
        return self.filter(result=InspectionResult.CONFIRMED)


class Inspection(OrganizationOwnedModel):
    """One verification of one property record."""

    objects = InspectionQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="inspections",
        verbose_name=_("property record"),
    )
    kind = models.CharField(
        _("kind"), max_length=20, choices=InspectionKind.choices, default=InspectionKind.ON_SITE
    )
    result = models.CharField(_("result"), max_length=20, choices=InspectionResult.choices)
    inspected_on = models.DateField(_("inspected on"), default=timezone.localdate)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inspections",
        verbose_name=_("inspector"),
    )
    # The role the inspector held at the time. Stored rather than looked up,
    # because a later role change must not rewrite the meaning of a past
    # inspection.
    inspector_role = models.CharField(
        _("inspector role"), max_length=32, choices=Role.choices, blank=True
    )

    observed_vacancy_status = models.CharField(
        _("observed occupancy"),
        max_length=32,
        choices=VacancyStatus.choices,
        default=VacancyStatus.UNKNOWN,
    )
    observed_condition = models.CharField(
        _("observed condition"),
        max_length=32,
        choices=ConditionGrade.choices,
        default=ConditionGrade.UNKNOWN,
    )
    observed_damage = models.JSONField(_("observed damage"), default=list, blank=True)

    findings = models.TextField(
        _("findings"),
        blank=True,
        help_text=_("What was established on site. Internal."),
    )
    applied_at = models.DateTimeField(_("applied to the record at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("verification")
        verbose_name_plural = _("verifications")
        ordering = ["-inspected_on", "-created_at"]
        indexes = [models.Index(fields=["result"])]

    def __str__(self):
        return f"{self.get_kind_display()} {self.inspected_on}: {self.get_result_display()}"

    @computed
    def assessment_source(self):
        """How much weight the observed condition carries.

        A verified contributor's visit is an observation; the administration's is
        an assessment. The register never blurs the two.
        """
        if self.inspector_role in {Role.VERIFIED_CONTRIBUTOR, ""}:
            return AssessmentSource.CITIZEN_OBSERVATION
        return AssessmentSource.STAFF_ASSESSMENT

    @computed
    def confirms_the_record(self):
        """Whether this inspection may move the record to confirmed.

        Citizens can verify — that is the point of the contributor role — but a
        confirmed vacancy is an official statement by the municipality, so a
        contributor's visit stops at "on-site check completed" and leaves the
        decision to the administration.
        """
        return (
            self.result == InspectionResult.CONFIRMED
            and self.inspector_role not in {Role.VERIFIED_CONTRIBUTOR, ""}
        )

    @computed
    def damage_labels(self):
        known = dict(DamageType.choices)
        return [known[value] for value in self.observed_damage if value in known]

    def apply_to_property(self, actor=None):
        """Write the findings onto the record and move its status accordingly.

        Returns the status transition, or None when the record's status did not
        change. Applying twice is harmless: the record simply already says this.
        """
        record = self.property

        if self.observed_condition != ConditionGrade.UNKNOWN:
            record.condition = self.observed_condition
            record.condition_source = self.assessment_source
            record.save(update_fields=["condition", "condition_source", "updated_at"])

        for damage_type in self.observed_damage or []:
            record.mark_damage(damage_type, source=self.assessment_source)

        if self.observed_vacancy_status != VacancyStatus.UNKNOWN:
            record.set_vacancy_status(
                self.observed_vacancy_status,
                actor=actor or self.inspector,
                source=str(self.get_kind_display()),
            )

        transition = self._advance_status(actor=actor or self.inspector)
        self._credit_participation(transition)

        # Written last, because a status change stamps today by default. What
        # matters here is when the object was actually looked at, which can be
        # well before the day the findings were typed in.
        record.last_checked_on = self.inspected_on
        record.save(update_fields=["last_checked_on", "updated_at"])

        self.applied_at = timezone.now()
        self.save(update_fields=["applied_at"])
        return transition

    def _credit_participation(self, transition):
        """Credit the people whose work this verification represents.

        Imported inside the method: participation is optional and this keeps the
        professional model free of a hard dependency on it.
        """
        from apps.participation.services import notify_confirmations_for, record_inspection

        record_inspection(self)
        if transition is not None and transition.to_status == RecordStatus.CONFIRMED:
            notify_confirmations_for(self.property, actor=self.inspector)

    def _advance_status(self, actor=None):
        record = self.property
        reason = _("Verification on %(date)s") % {"date": self.inspected_on.isoformat()}

        # The record has to be in the on-site check before a result can land, so
        # walk it there through the allowed steps rather than jumping.
        for intermediate in (RecordStatus.PRE_CHECK, RecordStatus.ON_SITE_CHECK):
            if record.status == RecordStatus.ARCHIVED:
                return None
            if record.status == intermediate:
                continue
            if record.can_transition_to(intermediate):
                record.transition_to(intermediate, actor=actor, reason=reason)

        target = RESULT_TO_STATUS[self.result]
        if target == RecordStatus.CONFIRMED and not self.confirms_the_record:
            # A contributor's confirmation is recorded but the record waits for
            # the administration.
            return None
        if record.can_transition_to(target):
            return record.transition_to(target, actor=actor, reason=reason)
        return None


class InspectionPhoto(models.Model):
    """A photograph taken during a verification. Internal unless released."""

    inspection = models.ForeignKey(
        Inspection, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(_("photo"), upload_to=inspection_photo_path)
    caption = models.CharField(_("caption"), max_length=255, blank=True)
    is_public = models.BooleanField(_("published"), default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("verification photo")
        verbose_name_plural = _("verification photos")
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.caption or f"Photo {self.pk}"
