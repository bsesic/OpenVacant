"""Records the data protection concept needs.

Two things live here that the domain apps cannot provide themselves: a log of who
looked at personal data, and evidence of consent. Both are about the
municipality being able to answer a question later — who saw this, and on what
basis did you hold it — which is precisely what cannot be reconstructed after
the fact.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AccessCategory(models.TextChoices):
    """Kinds of access worth recording.

    Only sensitive access is logged. Logging every page view would bury the
    entries that matter and would itself become a surveillance record of the
    staff.
    """

    REPORTER_CONTACT = "reporter_contact", _("Contact details of a reporter")
    OWNER_DATA = "owner_data", _("Owner data")
    INTERNAL_DOCUMENT = "internal_document", _("Internal document")
    INTERNAL_NOTES = "internal_notes", _("Internal notes")
    DATA_EXPORT = "data_export", _("Personal data export")
    BULK_EXPORT = "bulk_export", _("Bulk export")


class AccessLog(models.Model):
    """One recorded access to personal or internal data."""

    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="access_logs",
        verbose_name=_("tenant"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_logs",
        verbose_name=_("who"),
    )
    actor_label = models.CharField(
        _("who (recorded)"),
        max_length=255,
        blank=True,
        help_text=_("Kept as text so the entry survives the account being deleted."),
    )
    category = models.CharField(_("category"), max_length=32, choices=AccessCategory.choices)
    object_reference = models.CharField(
        _("object"),
        max_length=255,
        blank=True,
        help_text=_("Reference of the record or report concerned."),
    )
    purpose = models.CharField(_("purpose"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("access log entry")
        verbose_name_plural = _("access log")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        who = self.actor_label or str(self.actor) or "?"
        return f"{who} → {self.get_category_display()} ({self.object_reference})"


class ConsentPurpose(models.TextChoices):
    REPORT_SUBMISSION = "report_submission", _("Submitting a report")
    FEEDBACK_CONTACT = "feedback_contact", _("Being contacted about a report")
    NEWSLETTER = "newsletter", _("Newsletter")
    RECOGNITION = "recognition", _("Being named as a contributor")
    ANALYTICS = "analytics", _("Usage analytics")


class ConsentRecord(models.Model):
    """Evidence that consent was given, and that it can be withdrawn.

    A consent that cannot be shown is not much use, and one that cannot be
    withdrawn is not consent. Anonymous consents are keyed by a subject label
    (a report reference, for instance) because there is no account to attach to.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consents",
    )
    subject_label = models.CharField(
        _("subject"),
        max_length=255,
        blank=True,
        help_text=_("For consents without an account, e.g. a report reference."),
    )
    purpose = models.CharField(_("purpose"), max_length=32, choices=ConsentPurpose.choices)
    granted_at = models.DateTimeField(_("granted at"), default=timezone.now)
    withdrawn_at = models.DateTimeField(_("withdrawn at"), null=True, blank=True)
    source = models.CharField(
        _("source"),
        max_length=120,
        blank=True,
        help_text=_("Where it was given: report form, API, newsletter, settings."),
    )
    policy_version = models.CharField(
        _("policy version"),
        max_length=64,
        blank=True,
        help_text=_("Which version of the notice was shown at the time."),
    )

    class Meta:
        verbose_name = _("consent")
        verbose_name_plural = _("consents")
        ordering = ["-granted_at"]
        indexes = [models.Index(fields=["purpose"])]

    def __str__(self):
        state = _("withdrawn") if self.is_withdrawn else _("granted")
        return f"{self.subject or '?'}: {self.get_purpose_display()} ({state})"

    @property
    def subject(self):
        return self.user or self.subject_label

    @property
    def is_withdrawn(self):
        return self.withdrawn_at is not None

    @property
    def is_active(self):
        return not self.is_withdrawn

    def withdraw(self, when=None):
        if self.withdrawn_at is None:
            self.withdrawn_at = when or timezone.now()
            self.save(update_fields=["withdrawn_at"])
        return self
