from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.parcels.models import Parcel
from apps.properties.forms import (
    DamageForm,
    PropertyFilterForm,
    PropertyForm,
    StatusTransitionForm,
    VacancyStatusForm,
)
from apps.properties.models import Property, PropertyDamage
from apps.properties.search import search_properties
from apps.vacancies.models import vacancy_duration_days
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    StaffRoleRequiredMixin,
)


class PropertyListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    """The working list of records, with the same filters as the dashboard."""

    model = Property
    template_name = "properties/property_list.html"
    context_object_name = "properties"
    paginate_by = 25

    def get_filter_form(self):
        return PropertyFilterForm(
            self.request.GET or None, organization=self.request.organization
        )

    def get_queryset(self):
        queryset = super().get_queryset().select_related("district")
        form = self.get_filter_form()
        if not form.is_valid():
            return queryset
        data = form.cleaned_data
        # Internal wording is searchable here because this list is internal.
        queryset = search_properties(queryset, data.get("q"), include_internal=True)
        for field in ("status", "vacancy_status", "condition"):
            if data.get(field):
                queryset = queryset.filter(**{field: data[field]})
        if data.get("district"):
            queryset = queryset.filter(district_id=data["district"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["can_edit"] = self.request.organization.is_staff_member(self.request.user)
        return context


class PropertyDetailView(
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    DetailView,
):
    model = Property
    template_name = "properties/property_detail.html"
    context_object_name = "property_record"

    def get_queryset(self):
        return super().get_queryset().select_related("district").prefetch_related("parcels")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.object
        organization = self.request.organization
        context["damages"] = record.damages.all()
        context["transitions"] = record.status_transitions.select_related("actor")
        context["vacancy_periods"] = record.vacancy_periods.all()
        context["vacancy_days"] = vacancy_duration_days(record)
        context["can_edit"] = organization.is_staff_member(self.request.user)
        context["can_verify"] = organization.can_verify(self.request.user)
        context["inspections"] = record.inspections.select_related("inspector")
        context["open_tasks"] = record.tasks.open().select_related("assignee")
        context["spatial_contexts"] = record.spatial_contexts.select_related(
            "feature", "feature__layer"
        )
        context["heritage_checks"] = record.heritage_checks.all()
        context["documents"] = record.documents.select_related("uploaded_by")
        if context["can_edit"]:
            context["transition_form"] = StatusTransitionForm(instance=record)
            context["vacancy_form"] = VacancyStatusForm(instance=record)
            context["damage_form"] = DamageForm()
        return context


class PropertyCreateView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, OrgScopedQuerysetMixin, CreateView
):
    model = Property
    form_class = PropertyForm
    template_name = "properties/property_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Record %(reference)s created.") % {"reference": self.object.reference},
        )
        return response


class PropertyUpdateView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, OrgScopedQuerysetMixin, UpdateView
):
    model = Property
    form_class = PropertyForm
    template_name = "properties/property_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs


class _RecordActionView(CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, View):
    """Base for POST-only actions on one record of the current tenant."""

    def get_record(self, pk):
        return get_object_or_404(
            Property.objects.filter(organization=self.request.organization), pk=pk
        )


class PropertyTransitionView(_RecordActionView):
    """Change the workflow status, recording who changed it and why."""

    def post(self, request, pk):
        record = self.get_record(pk)
        form = StatusTransitionForm(request.POST, instance=record)
        if not form.is_valid():
            messages.error(request, _("That status change is not possible."))
            return redirect(record.get_absolute_url())
        try:
            record.transition_to(
                form.cleaned_data["status"],
                actor=request.user,
                reason=form.cleaned_data.get("reason", ""),
                note=form.cleaned_data.get("note", ""),
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
            return redirect(record.get_absolute_url())
        messages.success(request, _("Status updated."))
        return redirect(record.get_absolute_url())


class PropertyVacancyStatusView(_RecordActionView):
    """Record a change in occupancy, extending the vacancy history."""

    def post(self, request, pk):
        record = self.get_record(pk)
        form = VacancyStatusForm(request.POST, instance=record)
        if not form.is_valid():
            messages.error(request, _("Please choose an occupancy status."))
            return redirect(record.get_absolute_url())
        changed = record.set_vacancy_status(
            form.cleaned_data["vacancy_status"],
            actor=request.user,
            source=form.cleaned_data.get("source", ""),
            note=form.cleaned_data.get("note", ""),
        )
        if changed is None:
            messages.info(request, _("The occupancy status was already recorded as that."))
        else:
            messages.success(request, _("Occupancy recorded."))
        return redirect(record.get_absolute_url())


class PropertyDamageCreateView(_RecordActionView):
    def post(self, request, pk):
        record = self.get_record(pk)
        form = DamageForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Please choose a type of damage."))
            return redirect(record.get_absolute_url())
        record.mark_damage(
            form.cleaned_data["damage_type"],
            severity=form.cleaned_data["severity"],
            source=form.cleaned_data["source"],
            note=form.cleaned_data.get("note", ""),
        )
        messages.success(request, _("Damage recorded."))
        return redirect(record.get_absolute_url())


class PropertyDamageDeleteView(_RecordActionView):
    def post(self, request, pk, damage_pk):
        record = self.get_record(pk)
        damage = get_object_or_404(PropertyDamage, pk=damage_pk, property=record)
        damage.delete()
        messages.success(request, _("Damage removed."))
        return redirect(record.get_absolute_url())


class PropertyPublicationView(_RecordActionView):
    """Release a record for publication, or withdraw it again.

    Publication is a deliberate decision, so it is its own action rather than a
    checkbox that can be flipped in passing.
    """

    def post(self, request, pk):
        record = self.get_record(pk)
        record.is_public = not record.is_public
        record.save(update_fields=["is_public", "updated_at"])
        if record.is_public:
            messages.success(request, _("Record published."))
        else:
            messages.success(request, _("Record withdrawn from publication."))
        return redirect(record.get_absolute_url())


class PropertyHistoryView(
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    DetailView,
):
    """Full change history of one record."""

    model = Property
    template_name = "properties/property_history.html"
    context_object_name = "property_record"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history"] = self.object.history.all().select_related("history_user")
        context["transitions"] = self.object.status_transitions.select_related("actor")
        return context


class ParcelListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    """Parcels recorded for this municipality, mostly the result of an import."""

    model = Parcel
    template_name = "properties/parcel_list.html"
    context_object_name = "parcels"
    paginate_by = 50
