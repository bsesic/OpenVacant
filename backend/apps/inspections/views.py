from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import CreateView, ListView

from apps.inspections.forms import InspectionForm
from apps.inspections.models import Inspection, InspectionResult
from apps.properties.models import Property
from apps.workflows.models import TaskType, ensure_task
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    VerificationRoleRequiredMixin,
)


class InspectionCreateView(
    CurrentOrganizationRequiredMixin, VerificationRoleRequiredMixin, CreateView
):
    """Record a verification.

    Open to verified contributors as well as the administration — that is what
    the contributor role is for. Whether the result can confirm the record is
    decided by the inspection itself, from the role held at the time.
    """

    model = Inspection
    form_class = InspectionForm
    template_name = "inspections/inspection_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.record = None
        if request.user.is_authenticated and getattr(request, "organization", None):
            self.record = get_object_or_404(
                Property.objects.filter(organization=request.organization),
                pk=kwargs["property_pk"],
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["property_record"] = self.record
        context["may_confirm"] = self.request.organization.is_staff_member(self.request.user)
        return context

    def form_valid(self, form):
        organization = self.request.organization
        role = organization.get_role(self.request.user) or ""
        inspection = form.save(
            organization=organization,
            record=self.record,
            inspector=self.request.user,
            role=role,
        )
        inspection.apply_to_property(actor=self.request.user)

        if inspection.result == InspectionResult.CONFIRMED and not inspection.confirms_the_record:
            # A contributor confirmed on site; the decision itself is the
            # administration's, so leave them a task rather than a silent record.
            ensure_task(
                organization,
                TaskType.CHECK_PROPERTY,
                property=self.record,
                description=_("A verified contributor reported a confirmed vacancy."),
                created_by=self.request.user,
            )
            messages.success(
                self.request,
                _("Verification recorded. The administration will confirm the record."),
            )
        else:
            messages.success(self.request, _("Verification recorded."))
        return redirect(self.record.get_absolute_url())


class InspectionListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    model = Inspection
    template_name = "inspections/inspection_list.html"
    context_object_name = "inspections"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("property", "inspector")
