"""Recording access to personal and internal data."""

from compliance.models import AccessCategory, AccessLog


def log_access(actor, category, organization=None, object_reference="", purpose=""):
    """Record one access.

    The actor is also stored as text: an entry has to remain readable after the
    account is deleted, which is exactly when somebody is most likely to ask who
    saw a record.
    """
    return AccessLog.objects.create(
        organization=organization,
        actor=actor if getattr(actor, "pk", None) else None,
        actor_label=str(actor) if actor is not None else "",
        category=category,
        object_reference=object_reference[:255],
        purpose=purpose[:255],
    )


class LogSensitiveAccessMixin:
    """Log a view's access to sensitive data.

    Views declare ``access_category`` and, if the entry should name the object,
    override ``access_object_reference``. Only successful, authenticated access
    is recorded — a refused request discloses nothing.
    """

    access_category = AccessCategory.INTERNAL_NOTES
    access_purpose = ""

    def access_object_reference(self):
        obj = getattr(self, "object", None)
        return getattr(obj, "reference", "") or str(getattr(obj, "pk", "") or "")

    def should_log_access(self):
        return True

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self.request.user.is_authenticated and self.should_log_access():
            log_access(
                self.request.user,
                self.access_category,
                organization=getattr(self.request, "organization", None),
                object_reference=self.access_object_reference(),
                purpose=self.access_purpose,
            )
        return response
