from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.integrations.forms import ApiClientForm
from apps.integrations.models import ApiClient
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    OrganizationManagerRequiredMixin,
    OrgScopedQuerysetMixin,
)

# Where a freshly issued key is parked so the next page can show it once.
NEW_KEY_SESSION_KEY = "new_api_key"


class ApiClientListView(
    CurrentOrganizationRequiredMixin,
    OrganizationManagerRequiredMixin,
    OrgScopedQuerysetMixin,
    ListView,
):
    """Who has access to this municipality's data, and what they may do.

    Restricted to managers: this is the page that decides how far the
    municipality's data reaches.
    """

    model = ApiClient
    template_name = "integrations/client_list.html"
    context_object_name = "clients"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Shown once, immediately after issuing, then dropped.
        context["new_key"] = self.request.session.pop(NEW_KEY_SESSION_KEY, None)
        return context


class ApiClientCreateView(
    CurrentOrganizationRequiredMixin, OrganizationManagerRequiredMixin, CreateView
):
    model = ApiClient
    form_class = ApiClientForm
    template_name = "integrations/client_form.html"

    def form_valid(self, form):
        client, raw_key = ApiClient.issue(
            self.request.organization,
            name=form.cleaned_data["name"],
            scopes=form.cleaned_data["scope_choices"],
            description=form.cleaned_data.get("description", ""),
            contact_email=form.cleaned_data.get("contact_email", ""),
            expires_at=form.cleaned_data.get("expires_at"),
            throttle_rate=form.cleaned_data.get("throttle_rate") or "1000/hour",
            created_by=self.request.user,
        )
        # The key exists in readable form exactly once.
        self.request.session[NEW_KEY_SESSION_KEY] = {"name": client.name, "key": raw_key}
        messages.success(
            self.request,
            _("Client created. The key is shown once — store it now."),
        )
        return redirect(reverse("integrations:clients"))


class ApiClientUpdateView(
    CurrentOrganizationRequiredMixin,
    OrganizationManagerRequiredMixin,
    OrgScopedQuerysetMixin,
    UpdateView,
):
    model = ApiClient
    form_class = ApiClientForm
    template_name = "integrations/client_form.html"

    def form_valid(self, form):
        client = form.save(commit=False)
        client.scopes = form.cleaned_data["scope_choices"]
        client.save()
        messages.success(self.request, _("Client updated."))
        return redirect(reverse("integrations:clients"))


class _ClientActionView(
    CurrentOrganizationRequiredMixin, OrganizationManagerRequiredMixin, View
):
    def get_client(self, pk):
        return get_object_or_404(
            ApiClient.objects.filter(organization=self.request.organization), pk=pk
        )


class ApiClientRevokeView(_ClientActionView):
    """Withdraw a client's access. The municipality keeps the final say."""

    def post(self, request, pk):
        client = self.get_client(pk)
        client.revoke()
        messages.success(
            request, _("Access for %(name)s withdrawn.") % {"name": client.name}
        )
        return redirect(reverse("integrations:clients"))


class ApiClientReactivateView(_ClientActionView):
    def post(self, request, pk):
        client = self.get_client(pk)
        client.is_active = True
        client.revoked_at = None
        client.save(update_fields=["is_active", "revoked_at"])
        messages.success(request, _("Access restored."))
        return redirect(reverse("integrations:clients"))


class ApiClientRotateKeyView(_ClientActionView):
    """Issue a new key, invalidating the old one immediately."""

    def post(self, request, pk):
        client = self.get_client(pk)
        raw_key = client.rotate_key()
        request.session[NEW_KEY_SESSION_KEY] = {"name": client.name, "key": raw_key}
        messages.success(
            request, _("New key issued. The previous one no longer works.")
        )
        return redirect(reverse("integrations:clients"))
