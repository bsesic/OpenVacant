"""Federation with other instances.

Prepared for phase 5, inactive by default. The shape follows the one rule the
specification is firm about: each municipality decides for itself what leaves its
instance. So sharing is not a switch but a list of per-category permissions, and
there is no implicit "share everything".
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class PeerLevel(models.TextChoices):
    MUNICIPALITY = "municipality", _("Neighbouring municipality")
    DISTRICT = "district", _("District")
    STATE = "state", _("State")
    RESEARCH = "research", _("Research or statistics body")


class DataCategory(models.TextChoices):
    """What can be shared, at the granularity a municipality would decide on.

    Deliberately coarse and deliberately incomplete: personal data, owner
    information and internal notes have no category here, because they are not
    shareable at all.
    """

    PUBLISHED_RECORDS = "published_records", _("Published objects")
    AGGREGATE_STATISTICS = "aggregate_statistics", _("Aggregated key figures")
    ANONYMISED_RECORDS = "anonymised_records", _("Objects without free text")
    INCOMING_REPORTS = "incoming_reports", _("Reports routed to this instance")


class Direction(models.TextChoices):
    OUTBOUND = "outbound", _("We send")
    INBOUND = "inbound", _("We receive")


class PeerInstance(OrganizationOwnedModel):
    """Another OpenVacant instance this municipality is connected to."""

    objects = OrgQuerySet.as_manager()

    name = models.CharField(_("name"), max_length=255)
    level = models.CharField(
        _("level"), max_length=20, choices=PeerLevel.choices, default=PeerLevel.DISTRICT
    )
    base_url = models.URLField(
        _("base URL"), help_text=_("Root of the peer's API, e.g. https://example.de/api/v1/")
    )
    contact_email = models.EmailField(_("contact"), blank=True)
    # The credential this instance uses when calling the peer. Stored as a hash
    # of the same shape as an inbound key, so a dump of one instance does not
    # yield working access to another.
    outbound_key_hash = models.CharField(
        _("outbound key hash"), max_length=64, blank=True, editable=False
    )
    is_active = models.BooleanField(_("active"), default=False)
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("peer instance")
        verbose_name_plural = _("peer instances")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def shares(self, category, direction=Direction.OUTBOUND):
        """Whether this peer may have this category in this direction.

        Defaults to no. Nothing is shared unless somebody said so.
        """
        if not self.is_active:
            return False
        return self.share_scopes.filter(
            category=category, direction=direction, is_enabled=True
        ).exists()

    @computed
    def enabled_categories(self):
        return set(
            self.share_scopes.filter(is_enabled=True).values_list("category", flat=True)
        )


class ShareScope(models.Model):
    """One explicit permission: this peer, this category, this direction."""

    peer = models.ForeignKey(
        PeerInstance, on_delete=models.CASCADE, related_name="share_scopes"
    )
    category = models.CharField(_("category"), max_length=32, choices=DataCategory.choices)
    direction = models.CharField(
        _("direction"), max_length=10, choices=Direction.choices, default=Direction.OUTBOUND
    )
    is_enabled = models.BooleanField(_("enabled"), default=False)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="federation_decisions",
    )
    decided_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("share scope")
        verbose_name_plural = _("share scopes")
        ordering = ["peer", "category"]
        constraints = [
            models.UniqueConstraint(
                fields=["peer", "category", "direction"],
                name="unique_scope_per_peer_category_direction",
            )
        ]

    def __str__(self):
        state = _("enabled") if self.is_enabled else _("disabled")
        return f"{self.peer}: {self.get_category_display()} {self.direction} ({state})"


class SyncStatus(models.TextChoices):
    RUNNING = "running", _("Running")
    SUCCEEDED = "succeeded", _("Succeeded")
    FAILED = "failed", _("Failed")
    REFUSED = "refused", _("Refused by the peer")


class SyncRun(models.Model):
    """A record of one exchange with a peer, so sharing stays auditable."""

    peer = models.ForeignKey(PeerInstance, on_delete=models.CASCADE, related_name="sync_runs")
    direction = models.CharField(_("direction"), max_length=10, choices=Direction.choices)
    category = models.CharField(_("category"), max_length=32, choices=DataCategory.choices)
    status = models.CharField(
        _("status"), max_length=20, choices=SyncStatus.choices, default=SyncStatus.RUNNING
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    record_count = models.PositiveIntegerField(_("records"), default=0)
    message = models.TextField(_("message"), blank=True)

    class Meta:
        verbose_name = _("synchronisation run")
        verbose_name_plural = _("synchronisation runs")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.peer} {self.direction} {self.category}: {self.status}"

    def finish(self, status, record_count=0, message=""):
        self.status = SyncStatus(status)
        self.finished_at = timezone.now()
        self.record_count = record_count
        self.message = message
        self.save(update_fields=["status", "finished_at", "record_count", "message"])
        return self
