from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView

from apps.documents.forms import PropertyDocumentForm
from apps.documents.models import PropertyDocument, Visibility
from apps.properties.models import Property
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    StaffRoleRequiredMixin,
)


class DocumentListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    model = PropertyDocument
    template_name = "documents/document_list.html"
    context_object_name = "documents"
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("property", "uploaded_by")


class DocumentCreateView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, CreateView
):
    model = PropertyDocument
    form_class = PropertyDocumentForm
    template_name = "documents/document_form.html"

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
        return context

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        form.instance.property = self.record
        form.instance.uploaded_by = self.request.user
        form.save()
        messages.success(self.request, _("Document uploaded."))
        return redirect(self.record.get_absolute_url())


class DocumentDeleteView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, OrgScopedQuerysetMixin, DeleteView
):
    model = PropertyDocument
    template_name = "documents/document_confirm_delete.html"

    def get_success_url(self):
        return self.object.property.get_absolute_url()


class DocumentVisibilityView(CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, View):
    """Release a document or withdraw it again."""

    def post(self, request, pk):
        document = get_object_or_404(
            PropertyDocument.objects.filter(organization=request.organization), pk=pk
        )
        if not document.can_be_published:
            messages.error(request, _("Documents of this kind cannot be published."))
            return redirect(document.property.get_absolute_url())

        if document.visibility == Visibility.PUBLIC:
            document.visibility = Visibility.INTERNAL
            messages.success(request, _("Document withdrawn."))
        else:
            document.visibility = Visibility.PUBLIC
            if not document.property.is_public:
                messages.info(
                    request,
                    _(
                        "The document is released, but stays hidden until the record "
                        "itself is published."
                    ),
                )
            else:
                messages.success(request, _("Document released."))
        document.save(update_fields=["visibility"])
        return redirect(document.property.get_absolute_url())
