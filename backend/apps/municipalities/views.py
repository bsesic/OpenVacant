from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.views.generic.edit import FormView

from apps.municipalities.forms import DistrictForm, ModuleActivationForm, MunicipalityForm
from apps.municipalities.models import District, Municipality
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrganizationManagerRequiredMixin,
)


class CurrentMunicipalityMixin(CurrentOrganizationRequiredMixin):
    """Resolve the municipality profile of the tenant the user works in.

    A tenant without a profile is an incomplete setup rather than a permission
    problem, so this reports it as missing instead of silently showing an empty
    page.
    """

    def get_municipality(self):
        return get_object_or_404(Municipality, organization=self.request.organization)


class MunicipalityDetailView(
    CurrentMunicipalityMixin, InternalAreaRequiredMixin, DetailView
):
    """Read-only overview of the municipality's own configuration."""

    model = Municipality
    template_name = "municipalities/municipality_detail.html"
    context_object_name = "municipality_object"

    def get_object(self, queryset=None):
        municipality = self.get_municipality()
        if municipality.pk != self.kwargs["pk"]:
            raise PermissionDenied
        return municipality

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        municipality = self.object
        context["districts"] = municipality.districts.all()
        context["enabled_module_keys"] = municipality.enabled_modules()
        context["can_manage"] = self.request.organization.can_manage(self.request.user)
        return context


class MunicipalitySettingsView(
    CurrentMunicipalityMixin, OrganizationManagerRequiredMixin, UpdateView
):
    """Branding, contact details and legal texts, editable without code changes."""

    model = Municipality
    form_class = MunicipalityForm
    template_name = "municipalities/municipality_form.html"

    def get_object(self, queryset=None):
        return self.get_municipality()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Settings saved."))
        return response

    def get_success_url(self):
        return reverse("municipalities:detail", kwargs={"pk": self.object.pk})


class ModuleSettingsView(
    CurrentMunicipalityMixin, OrganizationManagerRequiredMixin, FormView
):
    """Switch the optional modules of this instance on or off."""

    form_class = ModuleActivationForm
    template_name = "municipalities/module_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["municipality"] = self.get_municipality()
        return kwargs

    def form_valid(self, form):
        municipality = form.save()
        messages.success(self.request, _("Modules updated."))
        return redirect(reverse("municipalities:detail", kwargs={"pk": municipality.pk}))


class DistrictListView(CurrentMunicipalityMixin, InternalAreaRequiredMixin, ListView):
    template_name = "municipalities/district_list.html"
    context_object_name = "districts"

    def get_queryset(self):
        return self.get_municipality().districts.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = self.request.organization.can_manage(self.request.user)
        return context


class DistrictCreateView(
    CurrentMunicipalityMixin, OrganizationManagerRequiredMixin, CreateView
):
    model = District
    form_class = DistrictForm
    template_name = "municipalities/district_form.html"
    success_url = reverse_lazy("municipalities:districts")

    def form_valid(self, form):
        form.instance.municipality = self.get_municipality()
        return super().form_valid(form)


class DistrictUpdateView(
    CurrentMunicipalityMixin, OrganizationManagerRequiredMixin, UpdateView
):
    model = District
    form_class = DistrictForm
    template_name = "municipalities/district_form.html"
    success_url = reverse_lazy("municipalities:districts")

    def get_queryset(self):
        return District.objects.filter(municipality=self.get_municipality())


class DistrictDeleteView(
    CurrentMunicipalityMixin, OrganizationManagerRequiredMixin, DeleteView
):
    model = District
    template_name = "municipalities/district_confirm_delete.html"
    success_url = reverse_lazy("municipalities:districts")

    def get_queryset(self):
        return District.objects.filter(municipality=self.get_municipality())
