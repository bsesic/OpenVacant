"""Tasks.

The register only helps if the work it implies is visible. A task is a small,
assignable piece of that work, attached to the record or report it concerns.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.properties.choices import Priority
from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class TaskType(models.TextChoices):
    """The recurring pieces of work named in the specification."""

    CHECK_PROPERTY = "check_property", _("Check the object")
    ON_SITE_APPOINTMENT = "on_site_appointment", _("Carry out an on-site appointment")
    VERIFY_HERITAGE = "verify_heritage", _("Verify the heritage status")
    CLARIFY_OWNERSHIP = "clarify_ownership", _("Clarify the ownership")
    UPDATE_PHOTO = "update_photo", _("Update the photograph")
    CHECK_FUNDING_AREA = "check_funding_area", _("Check the funding area")
    CHECK_PARCEL = "check_parcel", _("Check the parcel")
    CONTACT_OWNER = "contact_owner", _("Contact the owner")
    OTHER = "other", _("Other")


class TaskStatus(models.TextChoices):
    OPEN = "open", _("Open")
    IN_PROGRESS = "in_progress", _("In progress")
    DONE = "done", _("Done")
    CANCELLED = "cancelled", _("Cancelled")


OPEN_TASK_STATUSES = frozenset({TaskStatus.OPEN, TaskStatus.IN_PROGRESS})


class TaskQuerySet(OrgQuerySet):
    def open(self):
        return self.filter(status__in=OPEN_TASK_STATUSES)

    def overdue(self, on=None):
        return self.open().filter(due_on__lt=on or timezone.localdate())

    def assigned_to(self, user):
        return self.filter(assignee=user)

    def unassigned(self):
        return self.filter(assignee__isnull=True)


class Task(OrganizationOwnedModel):
    """One piece of work owed to a record or a report."""

    objects = TaskQuerySet.as_manager()

    task_type = models.CharField(
        _("type"), max_length=32, choices=TaskType.choices, default=TaskType.CHECK_PROPERTY
    )
    title = models.CharField(
        _("title"),
        max_length=255,
        blank=True,
        help_text=_("Leave empty to use the wording of the type."),
    )
    description = models.TextField(_("description"), blank=True)
    property = models.ForeignKey(
        "properties.Property",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name=_("property record"),
    )
    report = models.ForeignKey(
        "reports.Report",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name=_("report"),
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
        verbose_name=_("assigned to"),
    )
    status = models.CharField(
        _("status"), max_length=20, choices=TaskStatus.choices, default=TaskStatus.OPEN
    )
    priority = models.CharField(
        _("priority"), max_length=16, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_on = models.DateField(_("due on"), null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
    )
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    completion_note = models.TextField(_("completion note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        ordering = ["status", "due_on", "-priority", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["due_on"]),
        ]

    def __str__(self):
        return self.label

    @computed
    def label(self):
        return self.title or str(TaskType(self.task_type).label)

    @computed
    def is_open(self):
        return self.status in OPEN_TASK_STATUSES

    @computed
    def is_overdue(self):
        return bool(self.is_open and self.due_on and self.due_on < timezone.localdate())

    def complete(self, actor=None, note=""):
        self.status = TaskStatus.DONE
        self.completed_at = timezone.now()
        if note:
            self.completion_note = note
        if actor is not None and self.assignee_id is None:
            # Whoever finished an unassigned task becomes its owner in hindsight,
            # so the record shows who did the work.
            self.assignee = actor
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "completion_note",
                "assignee",
                "updated_at",
            ]
        )
        return self

    def reopen(self):
        self.status = TaskStatus.OPEN
        self.completed_at = None
        self.save(update_fields=["status", "completed_at", "updated_at"])
        return self


def ensure_task(organization, task_type, property=None, report=None, **extra):
    """Create a task unless an open one of the same type already exists.

    Called from the report and verification flows, where the same task would
    otherwise be created again every time somebody touches the record.
    """
    existing = Task.objects.filter(
        organization=organization,
        task_type=task_type,
        property=property,
        report=report,
        status__in=OPEN_TASK_STATUSES,
    ).first()
    if existing is not None:
        return existing
    return Task.objects.create(
        organization=organization,
        task_type=task_type,
        property=property,
        report=report,
        **extra,
    )
