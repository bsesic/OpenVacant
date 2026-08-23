"""External API clients.

The municipality decides which outside system may read or write what, and can
withdraw that at any time. Two things follow from that and shape this module:
a client's rights are an explicit list of scopes rather than "API access", and
the key itself is stored only as a hash, so a database dump does not hand
somebody working credentials.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

# Shown in the interface and used to find the right row without the secret.
KEY_PREFIX_LENGTH = 8


class Scope(models.TextChoices):
    """What an external client is allowed to do.

    Deliberately fine-grained: an open-data portal needs published objects and
    nothing else, while a municipal GIS may need the professional data. Granting
    one must not imply the other.
    """

    READ_PUBLIC = "read_public", _("Read published objects")
    READ_STATISTICS = "read_statistics", _("Read key figures")
    READ_INTERNAL = "read_internal", _("Read professional data")
    WRITE_REPORTS = "write_reports", _("Submit reports")
    READ_GEODATA = "read_geodata", _("Read geodata layers")


# Scopes that expose data beyond what anyone could see on the public map. These
# are the ones a municipality should have to think about before granting.
SENSITIVE_SCOPES = frozenset({Scope.READ_INTERNAL})


def generate_key():
    """A new API key. Returned once, never stored in this form."""
    return f"ov_{secrets.token_urlsafe(32)}"


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiClientQuerySet(OrgQuerySet):
    def usable(self):
        """Clients that may authenticate right now."""
        now = timezone.now()
        return self.filter(is_active=True).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )


class ApiClient(OrganizationOwnedModel):
    """One external system with scoped, revocable access to a municipality."""

    objects = ApiClientQuerySet.as_manager()

    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(
        _("purpose"),
        blank=True,
        help_text=_("What this client is for. Useful when reviewing access later."),
    )
    contact_email = models.EmailField(
        _("contact"),
        blank=True,
        help_text=_("Who to reach if the access has to be withdrawn."),
    )
    key_prefix = models.CharField(_("key prefix"), max_length=16, editable=False)
    key_hash = models.CharField(_("key hash"), max_length=64, editable=False)
    scopes = models.JSONField(_("scopes"), default=list)
    is_active = models.BooleanField(_("active"), default=True)
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        help_text=_("Leave empty for access without an end date."),
    )
    throttle_rate = models.CharField(
        _("rate limit"),
        max_length=32,
        default="1000/hour",
        help_text=_("Requests per period for this client, e.g. 1000/hour."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_api_clients",
    )
    last_used_at = models.DateTimeField(_("last used"), null=True, blank=True)
    request_count = models.PositiveBigIntegerField(_("requests"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    class Meta:
        verbose_name = _("API client")
        verbose_name_plural = _("API clients")
        ordering = ["name"]
        indexes = [models.Index(fields=["key_prefix"])]

    def __str__(self):
        return self.name

    # --- Key handling -----------------------------------------------------
    @classmethod
    def issue(cls, organization, name, scopes, **extra):
        """Create a client and return it together with its key.

        The key is returned exactly once. There is no way to recover it later,
        which is the point: a lost key is replaced, not looked up.
        """
        raw_key = generate_key()
        client = cls.objects.create(
            organization=organization,
            name=name,
            scopes=list(scopes),
            key_prefix=raw_key[:KEY_PREFIX_LENGTH],
            key_hash=hash_key(raw_key),
            **extra,
        )
        return client, raw_key

    def rotate_key(self):
        """Replace the key, invalidating the old one immediately."""
        raw_key = generate_key()
        self.key_prefix = raw_key[:KEY_PREFIX_LENGTH]
        self.key_hash = hash_key(raw_key)
        self.save(update_fields=["key_prefix", "key_hash"])
        return raw_key

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])
        return self

    # --- State ------------------------------------------------------------
    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_usable(self):
        return self.is_active and not self.is_expired

    def has_scope(self, scope):
        return scope in (self.scopes or [])

    @property
    def scope_labels(self):
        known = dict(Scope.choices)
        return [str(known[scope]) for scope in (self.scopes or []) if scope in known]

    @property
    def grants_internal_data(self):
        """Whether this client can see more than the public map shows."""
        return bool(SENSITIVE_SCOPES.intersection(self.scopes or []))

    def record_use(self):
        """Note that the client was used, for the access review."""
        ApiClient.objects.filter(pk=self.pk).update(
            last_used_at=timezone.now(), request_count=models.F("request_count") + 1
        )
