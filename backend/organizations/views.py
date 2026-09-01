from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from organizations.forms import InvitationForm, OrganizationForm
from organizations.middleware import SESSION_KEY
from organizations.models import Invitation, Organization, Role
from users.emails import send_transactional_mail


def _user_orgs(user):
    return Organization.objects.filter(memberships__user=user).distinct()


class OrganizationListView(LoginRequiredMixin, ListView):
    template_name = "organizations/organization_list.html"
    context_object_name = "organizations"

    def get_queryset(self):
        return _user_orgs(self.request.user)


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    """Create a tenant. Reserved for the instance operator.

    Municipalities are onboarded by whoever runs the instance, not by whoever
    signs up, so this is limited to Django staff accounts.
    """

    form_class = OrganizationForm
    template_name = "organizations/organization_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.add_member(self.request.user, role=Role.OWNER)
        self.request.session[SESSION_KEY] = self.object.pk
        messages.success(self.request, _("Organization created."))
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    template_name = "organizations/organization_detail.html"
    context_object_name = "organization"

    def get_queryset(self):
        return _user_orgs(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.object
        context["memberships"] = org.memberships.select_related("user")
        context["pending_invitations"] = org.invitations.filter(accepted_at__isnull=True)
        context["user_role"] = org.get_role(self.request.user)
        context["can_manage"] = org.can_manage(self.request.user)
        context["invite_form"] = InvitationForm()
        return context


class _ManagedOrgMixin(LoginRequiredMixin):
    """Resolve the slug organization and require manage rights on it."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.organization = get_object_or_404(_user_orgs(request.user), slug=kwargs["slug"])
        if not self.organization.can_manage(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class InvitationCreateView(_ManagedOrgMixin, CreateView):
    form_class = InvitationForm
    template_name = "organizations/invitation_form.html"

    def form_valid(self, form):
        form.instance.organization = self.organization
        form.instance.invited_by = self.request.user
        response = super().form_valid(form)
        accept_url = self.request.build_absolute_uri(self.object.get_accept_url())
        send_transactional_mail(
            subject_template="emails/invitation_subject.txt",
            body_template="emails/invitation_body.txt",
            context={"invitation": self.object, "accept_url": accept_url},
            recipient_list=[self.object.email],
        )
        messages.success(self.request, _("Invitation sent."))
        return response

    def get_success_url(self):
        return self.organization.get_absolute_url()


class RemoveMembershipView(_ManagedOrgMixin, View):
    def post(self, request, slug, pk):
        membership = get_object_or_404(self.organization.memberships, pk=pk)
        owners = self.organization.memberships.filter(role=Role.OWNER).count()
        if membership.role == Role.OWNER and owners <= 1:
            messages.error(request, _("You cannot remove the last owner."))
        else:
            membership.delete()
            messages.success(request, _("Member removed."))
        return redirect(self.organization.get_absolute_url())


class SwitchOrganizationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        org = get_object_or_404(_user_orgs(request.user), pk=pk)
        request.session[SESSION_KEY] = org.pk
        messages.success(request, _("Switched to %(name)s.") % {"name": org.name})
        return redirect(org.get_absolute_url())


class AcceptInvitationView(LoginRequiredMixin, View):
    def get(self, request, token):
        invitation = get_object_or_404(Invitation, token=token, accepted_at__isnull=True)
        return render(
            request,
            "organizations/accept_invitation.html",
            {"invitation": invitation},
        )

    def post(self, request, token):
        invitation = get_object_or_404(Invitation, token=token, accepted_at__isnull=True)
        invitation.accept(request.user)
        request.session[SESSION_KEY] = invitation.organization.pk
        messages.success(
            request,
            _("You have joined %(name)s.") % {"name": invitation.organization.name},
        )
        return redirect(invitation.organization.get_absolute_url())
