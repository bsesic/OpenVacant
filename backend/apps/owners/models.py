"""Owners and ownership claims.

Prepared for phase 2, inactive by default. It is here now because the phase-2
owner portal must not require a schema redesign, and because the research the
administration already does today — who owns this, has anyone reached them — has
nowhere else to live.

Everything in this module is personal data about identifiable people and is
therefore internal without exception. Nothing here is ever published, and the
public API has no serializer for any of it.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

computed = property


class OwnerKind(models.TextChoices):
    PRIVATE = "private", _("Private individual")
    COMPANY = "company", _("Company")
    COMMUNITY_OF_HEIRS = "community_of_heirs", _("Community of heirs")
    PUBLIC_BODY = "public_body", _("Public body")
    CHURCH = "church", _("Church or foundation")
    ASSOCIATION = "association", _("Association")
    UNKNOWN = "unknown", _("Unknown")


class ContactState(models.TextChoices):
    """How far the administration has got in reaching the owner.

    The specification asks for exactly this: whether the owner is known, whether
    there is a contact, and what contact attempts have been made.
    """

    UNKNOWN = "unknown", _("Owner unknown")
    IDENTIFIED = "identified", _("Owner identified, no contact details")
    CONTACTABLE = "contactable", _("Contact details available")
    CONTACTED = "contacted", _("Contact attempted")
    IN_DIALOGUE = "in_dialogue", _("In dialogue")
    UNREACHABLE = "unreachable", _("Not reachable")


class Owner(OrganizationOwnedModel):
    """An owner as far as the administration knows them. Internal only."""

    objects = OrgQuerySet.as_manager()

    kind = models.CharField(
        _("kind"), max_length=32, choices=OwnerKind.choices, default=OwnerKind.UNKNOWN
    )
    name = models.CharField(_("name"), max_length=255, blank=True)
    contact_state = models.CharField(
        _("contact state"),
        max_length=20,
        choices=ContactState.choices,
        default=ContactState.UNKNOWN,
    )
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=50, blank=True)
    postal_address = models.TextField(_("postal address"), blank=True)
    representative = models.CharField(
        _("representative"),
        max_length=255,
        blank=True,
        help_text=_("Administrator, agent or spokesperson of a community of heirs."),
    )
    note = models.TextField(_("internal note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("owner")
        verbose_name_plural = _("owners")
        ordering = ["name"]

    def __str__(self):
        return self.name or str(self.get_kind_display())

    @computed
    def is_reachable(self):
        return self.contact_state in (
            ContactState.CONTACTABLE,
            ContactState.CONTACTED,
            ContactState.IN_DIALOGUE,
        )


class Ownership(OrganizationOwnedModel):
    """A link between an owner and a property, as the administration recorded it."""

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="ownerships",
        verbose_name=_("property record"),
    )
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="ownerships")
    share = models.CharField(
        _("share"),
        max_length=64,
        blank=True,
        help_text=_("Where ownership is divided, e.g. among heirs."),
    )
    source = models.CharField(
        _("source"),
        max_length=255,
        blank=True,
        help_text=_("How this was established. Never a land registry extract in public data."),
    )
    recorded_on = models.DateField(_("recorded on"), default=timezone.localdate)
    note = models.TextField(_("internal note"), blank=True)

    class Meta:
        verbose_name = _("ownership")
        verbose_name_plural = _("ownerships")
        ordering = ["-recorded_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "owner"], name="unique_ownership_per_property_owner"
            )
        ]

    def __str__(self):
        return f"{self.owner} — {self.property_id}"


class ClaimStatus(models.TextChoices):
    PENDING = "pending", _("Awaiting review")
    VERIFIED = "verified", _("Verified")
    REJECTED = "rejected", _("Rejected")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class OwnershipClaim(OrganizationOwnedModel):
    """Somebody claiming to own an object, for the phase-2 owner portal.

    A claim is never self-verifying. Letting an account assert ownership and act
    on it would hand a stranger the ability to speak for a building, so a claim
    only takes effect once the administration has confirmed it.
    """

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="ownership_claims",
        verbose_name=_("property record"),
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ownership_claims",
        verbose_name=_("claimant"),
    )
    owner = models.ForeignKey(
        Owner,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claims",
        help_text=_("Set once the claim has been matched to a known owner."),
    )
    status = models.CharField(
        _("status"), max_length=20, choices=ClaimStatus.choices, default=ClaimStatus.PENDING
    )
    evidence_note = models.TextField(
        _("evidence"),
        blank=True,
        help_text=_("What the claimant offered as proof. Never stored as a document here."),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_ownership_claims",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(_("review note"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("ownership claim")
        verbose_name_plural = _("ownership claims")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "claimant"],
                condition=models.Q(status__in=["pending", "verified"]),
                name="unique_open_claim_per_property_claimant",
            )
        ]

    def __str__(self):
        return f"{self.claimant} → {self.property_id} ({self.status})"

    @computed
    def is_effective(self):
        """Whether this claim actually grants the claimant standing."""
        return self.status == ClaimStatus.VERIFIED

    def review(self, status, actor=None, note=""):
        self.status = ClaimStatus(status)
        self.reviewed_by = actor
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
        return self


class InterestKind(models.TextChoices):
    SELL = "sell", _("Willing to sell")
    LET = "let", _("Willing to let")
    RENOVATE = "renovate", _("Intends to renovate")
    SUPPORT_NEEDED = "support_needed", _("Needs support")
    DEVELOP_TOGETHER = "develop_together", _("Open to joint development")
    NO_INTEREST = "no_interest", _("No interest at present")


class OwnerInterest(OrganizationOwnedModel):
    """What an owner has said they want to do with the object."""

    objects = OrgQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="owner_interests",
        verbose_name=_("property record"),
    )
    owner = models.ForeignKey(
        Owner, null=True, blank=True, on_delete=models.SET_NULL, related_name="interests"
    )
    kind = models.CharField(_("interest"), max_length=32, choices=InterestKind.choices)
    stated_on = models.DateField(_("stated on"), default=timezone.localdate)
    note = models.TextField(_("note"), blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_owner_interests",
    )

    class Meta:
        verbose_name = _("owner interest")
        verbose_name_plural = _("owner interests")
        ordering = ["-stated_on"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.stated_on})"
