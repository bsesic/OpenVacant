from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, UpdateView

from users.forms import ProfileForm


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "profile/profile.html"


class ProfileUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = ProfileForm
    template_name = "profile/profile_form.html"
    success_url = reverse_lazy("profile")
    success_message = _("Your profile has been updated.")

    def get_object(self, queryset=None):
        return self.request.user
