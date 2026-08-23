"""Files attached to a property record.

The register holds two kinds of file about the same building. A photograph of a
boarded-up shopfront can be published; an expert report, a letter to the owner
or a land registry extract cannot. Visibility is therefore a field on the
document and is enforced in the queryset, not decided in a template.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from organizations.models import OrgQuerySet, OrganizationOwnedModel

# PropertyDocument carries a field called ``property``, which shadows the builtin
# inside the class body; keep a reference for computed attributes.
computed = property


class DocumentKind(models.TextChoices):
    PHOTO = "photo", _("Photograph")
    SITE_PLAN = "site_plan", _("Site plan")
    EXPERT_REPORT = "expert_report", _("Expert report")
    CORRESPONDENCE = "correspondence", _("Correspondence")
    PERMIT = "permit", _("Permit or notice")
    LAND_REGISTRY = "land_registry", _("Land registry extract")
    OTHER = "other", _("Other")


# Kinds that must never be publishable, whatever anyone ticks. Correspondence
# and land registry extracts are about identifiable people by their nature, and
# an expert report is the municipality's own commissioned work.
NEVER_PUBLIC_KINDS = frozenset(
    {
        DocumentKind.CORRESPONDENCE,
        DocumentKind.LAND_REGISTRY,
        DocumentKind.EXPERT_REPORT,
    }
)


class Visibility(models.TextChoices):
    INTERNAL = "internal", _("Internal")
    PUBLIC = "public", _("Public")


def document_upload_path(instance, filename):
    return f"documents/org_{instance.organization_id}/property_{instance.property_id}/{filename}"


class DocumentQuerySet(OrgQuerySet):
    def public(self):
        """Documents that may be shown outside the administration.

        Both the document and its record have to be released: a public photo of
        an unpublished object would disclose the object itself.
        """
        return self.filter(visibility=Visibility.PUBLIC, property__is_public=True)

    def internal(self):
        return self.exclude(visibility=Visibility.PUBLIC)

    def photos(self):
        return self.filter(kind=DocumentKind.PHOTO)


class PropertyDocument(OrganizationOwnedModel):
    """One file belonging to a property record."""

    objects = DocumentQuerySet.as_manager()

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("property record"),
    )
    kind = models.CharField(
        _("kind"), max_length=32, choices=DocumentKind.choices, default=DocumentKind.PHOTO
    )
    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    file = models.FileField(_("file"), upload_to=document_upload_path)
    visibility = models.CharField(
        _("visibility"),
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.INTERNAL,
        help_text=_("Documents are internal unless released deliberately."),
    )
    recorded_on = models.DateField(_("document date"), null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["kind"]),
            models.Index(fields=["visibility"]),
        ]

    def __str__(self):
        return self.title

    @computed
    def is_public(self):
        """Whether this file is actually visible outside the administration."""
        return self.visibility == Visibility.PUBLIC and self.property.is_public

    @computed
    def can_be_published(self):
        return self.kind not in NEVER_PUBLIC_KINDS

    @computed
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1] if self.file else ""

    def save(self, *args, **kwargs):
        # Enforced here rather than only in the form, so an import or a shell
        # session cannot publish a letter by setting a field.
        if not self.can_be_published:
            self.visibility = Visibility.INTERNAL
        return super().save(*args, **kwargs)
