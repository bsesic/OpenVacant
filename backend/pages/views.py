from django.contrib import messages
from django.core.mail import mail_admins
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView, TemplateView
from django_ratelimit.decorators import ratelimit

from pages.forms import ContactForm


class HomeView(TemplateView):
    template_name = "pages/home.html"


class AboutView(TemplateView):
    template_name = "pages/about.html"


class FaqView(TemplateView):
    template_name = "pages/faq.html"


class ImprintView(TemplateView):
    template_name = "pages/imprint.html"


class PrivacyView(TemplateView):
    template_name = "pages/privacy.html"


class TermsView(TemplateView):
    template_name = "pages/terms.html"


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class ContactView(FormView):
    template_name = "pages/contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("pages:contact")

    def form_valid(self, form):
        data = form.cleaned_data
        mail_admins(
            subject=_("Contact form: %(name)s") % {"name": data["name"]},
            message="From: {name} <{email}>\n\n{message}".format(**data),
        )
        messages.success(self.request, _("Thanks for your message. We'll be in touch."))
        return super().form_valid(form)
