from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, ListView, UpdateView

from apps.heritage.forms import HeritageCheckForm, MonumentForm
from apps.heritage.models import HeritageCheck, MonumentRecord
from apps.municipalities.models import Module
from apps.properties.models import Property
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    StaffRoleRequiredMixin,
)


class HeritageModuleRequiredMixin:
    """Refuse when the municipality has switched the heritage module off."""

    def dispatch(self, request, *args, **kwargs):
        municipality = getattr(request, "municipality", None) or None
        if municipality is not None and not municipality.module_enabled(Module.HERITAGE):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class MonumentListView(
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    HeritageModuleRequiredMixin,
    OrgScopedQuerysetMixin,
    ListView,
):
    model = MonumentRecord
    template_name = "heritage/monument_list.html"
    context_object_name = "monuments"
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("property")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit"] = self.request.organization.is_staff_member(self.request.user)
        # Listed monuments standing empty are the cases that lose fabric fastest.
        context["vacant_monuments"] = (
            Property.objects.for_organization(self.request.organization)
            .filter(is_heritage_protected=True)
            .vacant()
            .count()
        )
        return context


class MonumentCreateView(
    CurrentOrganizationRequiredMixin,
    StaffRoleRequiredMixin,
    HeritageModuleRequiredMixin,
    OrgScopedQuerysetMixin,
    CreateView,
):
    model = MonumentRecord
    form_class = MonumentForm
    template_name = "heritage/monument_form.html"
    success_url = reverse_lazy("heritage:monuments")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs


class MonumentUpdateView(
    CurrentOrganizationRequiredMixin,
    StaffRoleRequiredMixin,
    HeritageModuleRequiredMixin,
    OrgScopedQuerysetMixin,
    UpdateView,
):
    model = MonumentRecord
    form_class = MonumentForm
    template_name = "heritage/monument_form.html"
    success_url = reverse_lazy("heritage:monuments")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs


class HeritageCheckCreateView(
    CurrentOrganizationRequiredMixin,
    StaffRoleRequiredMixin,
    HeritageModuleRequiredMixin,
    CreateView,
):
    """Record the answer from the heritage authority for one object."""

    model = HeritageCheck
    form_class = HeritageCheckForm
    template_name = "heritage/check_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.record = None
        if request.user.is_authenticated and getattr(request, "organization", None):
            self.record = get_object_or_404(
                Property.objects.filter(organization=request.organization),
                pk=kwargs["property_pk"],
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["property_record"] = self.record
        return context

    def form_valid(self, form):
        check = form.save(commit=False)
        check.organization = self.request.organization
        check.property = self.record
        check.checked_by = self.request.user
        check.save()
        if check.apply_to_property():
            messages.success(self.request, _("Check recorded and the record updated."))
        else:
            messages.success(self.request, _("Check recorded."))
        return redirect(self.record.get_absolute_url())
