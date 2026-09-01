import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Membership roles inside a tenant (a municipality or a higher authority).

    The first three are the tenant administration roles inherited from the
    platform foundation. The rest model the municipal departments and external
    bodies named in the specification, so a municipality decides per person
    which professional data they may see.
    """

    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Administrator")
    MEMBER = "member", _("Member")
    # Municipal departments.
    BUILDING_AUTHORITY = "building_authority", _("Building authority")
    URBAN_PLANNING = "urban_planning", _("Urban planning")
    PROPERTY_MANAGEMENT = "property_management", _("Property management")
    ECONOMIC_DEVELOPMENT = "economic_development", _("Economic development")
    REGULATORY_OFFICE = "regulatory_office", _("Regulatory office")
    HERITAGE_AUTHORITY = "heritage_authority", _("Heritage authority")
    # External public bodies (district, state offices) with limited access.
    EXTERNAL_AGENCY = "external_agency", _("External public body")
    # Citizens who were cleared for verification work.
    VERIFIED_CONTRIBUTOR = "verified_contributor", _("Verified contributor")
    # Property owners, for the owner portal prepared for a later phase.
    OWNER_REPRESENTATIVE = "owner_representative", _("Property owner")


# Roles allowed to manage members, invitations and municipality settings.
MANAGER_ROLES = {Role.OWNER, Role.ADMIN}

# Roles working inside the administration. These may see internal professional
# data (research notes, owner information, internal documents).
STAFF_ROLES = {
    Role.OWNER,
    Role.ADMIN,
    Role.MEMBER,
    Role.BUILDING_AUTHORITY,
    Role.URBAN_PLANNING,
    Role.PROPERTY_MANAGEMENT,
    Role.ECONOMIC_DEVELOPMENT,
    Role.REGULATORY_OFFICE,
    Role.HERITAGE_AUTHORITY,
}

# Roles allowed to record a verification result for a property.
VERIFICATION_ROLES = STAFF_ROLES | {Role.VERIFIED_CONTRIBUTOR}

# Roles that may be assigned a task.
ASSIGNABLE_ROLES = VERIFICATION_ROLES

# Roles with read access to professional data but no editing rights.
READ_ONLY_ROLES = {Role.EXTERNAL_AGENCY}

# Every role that grants access to the administration area at all.
INTERNAL_ROLES = STAFF_ROLES | READ_ONLY_ROLES


def generate_invite_token():
    return secrets.token_urlsafe(32)


class Organization(models.Model):
    """A tenant: a municipality or a higher authority running the register.

    The professional profile of a municipality (branding, districts, boundary)
    lives in the ``municipalities`` app; this model only carries the tenancy
    itself so that non-municipal tenants — a district or a state office in a
    federated setup — reuse the same membership machinery.
    """

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Membership",
        related_name="organizations",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.name) or "org"
        slug = base
        i = 2
        while Organization.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        return slug

    def get_absolute_url(self):
        return reverse("organizations:detail", kwargs={"slug": self.slug})

    def add_member(self, user, role=Role.MEMBER):
        membership, _created = Membership.objects.get_or_create(
            organization=self, user=user, defaults={"role": role}
        )
        return membership

    def get_role(self, user):
        if not user or not user.is_authenticated:
            return None
        membership = self.memberships.filter(user=user).first()
        return membership.role if membership else None

    def has_member(self, user):
        return self.get_role(user) is not None

    def can_manage(self, user):
        return self.get_role(user) in MANAGER_ROLES

    def is_staff_member(self, user):
        """True when the user may edit professional data for this tenant."""
        return self.get_role(user) in STAFF_ROLES

    def has_internal_access(self, user):
        """True when the user may see the administration area at all."""
        return self.get_role(user) in INTERNAL_ROLES

    def can_verify(self, user):
        """True when the user may record a verification result."""
        return self.get_role(user) in VERIFICATION_ROLES


class Membership(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "user")
        ordering = ["organization", "user"]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"

    @property
    def is_owner(self):
        return self.role == Role.OWNER


class Invitation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=generate_invite_token)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} -> {self.organization} ({self.role})"

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    def get_accept_url(self):
        return reverse("organizations:accept_invitation", kwargs={"token": self.token})

    def accept(self, user):
        """Turn the invitation into a membership for ``user``."""
        membership = self.organization.add_member(user, role=self.role)
        self.accepted_at = timezone.now()
        self.save(update_fields=["accepted_at"])
        return membership


class OrgQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)


class OrganizationOwnedModel(models.Model):
    """Abstract base for any tenant-scoped model.

    Inherit from this and use ``Model.objects.for_organization(org)`` (or the
    OrgScopedQuerysetMixin) to keep data isolated per tenant.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="+")

    objects = OrgQuerySet.as_manager()

    class Meta:
        abstract = True
