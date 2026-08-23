from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from organizations.models import (
    INTERNAL_ROLES,
    MANAGER_ROLES,
    STAFF_ROLES,
    VERIFICATION_ROLES,
)


class CurrentOrganizationRequiredMixin(LoginRequiredMixin):
    """Require an authenticated user who belongs to a tenant.

    Unlike a self-service product, tenants here are municipalities created by the
    instance operator. A user without a membership is a citizen and simply has no
    business in the administration area, so this denies instead of offering to
    create one.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request, "organization", None) is None:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class OrgScopedQuerysetMixin:
    """Scope a generic view's queryset and new objects to the current tenant.

    Use on views whose model inherits ``OrganizationOwnedModel`` (or has an
    ``organization`` FK). Combine with CurrentOrganizationRequiredMixin.
    """

    def get_queryset(self):
        return super().get_queryset().filter(organization=self.request.organization)

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        return super().form_valid(form)


class RoleRequiredMixin:
    """Require the current user to hold one of ``required_roles`` in the tenant."""

    required_roles = frozenset()

    def dispatch(self, request, *args, **kwargs):
        org = getattr(request, "organization", None)
        if org is None or org.get_role(request.user) not in self.required_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class OrganizationManagerRequiredMixin(RoleRequiredMixin):
    """Require owner/administrator rights on the active tenant."""

    required_roles = MANAGER_ROLES


class InternalAreaRequiredMixin(RoleRequiredMixin):
    """Require any role that grants access to the administration area."""

    required_roles = INTERNAL_ROLES


class StaffRoleRequiredMixin(RoleRequiredMixin):
    """Require a role that may edit professional data (excludes read-only bodies)."""

    required_roles = STAFF_ROLES


class VerificationRoleRequiredMixin(RoleRequiredMixin):
    """Require a role that may record verification results."""

    required_roles = VERIFICATION_ROLES
