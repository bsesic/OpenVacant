from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView

from newsletter import providers
from newsletter.forms import SubscribeForm
from newsletter.models import Subscriber
from users.emails import send_transactional_mail


class SubscribeView(FormView):
    template_name = "newsletter/subscribe.html"
    form_class = SubscribeForm
    success_url = reverse_lazy("newsletter:subscribe")

    def form_valid(self, form):
        subscriber, _created = Subscriber.objects.get_or_create(email=form.cleaned_data["email"])
        confirm_url = self.request.build_absolute_uri(
            reverse_lazy("newsletter:confirm", kwargs={"token": subscriber.token})
        )
        send_transactional_mail(
            subject_template="emails/newsletter_confirm_subject.txt",
            body_template="emails/newsletter_confirm_body.txt",
            context={"confirm_url": confirm_url},
            recipient_list=[subscriber.email],
        )
        messages.success(self.request, _("Please check your inbox to confirm your subscription."))
        return super().form_valid(form)


class ConfirmView(View):
    def get(self, request, token):
        subscriber = get_object_or_404(Subscriber, token=token)
        subscriber.confirmed = True
        subscriber.unsubscribed_at = None
        subscriber.save(update_fields=["confirmed", "unsubscribed_at"])
        providers.sync_subscriber(subscriber)
        return render(request, "newsletter/confirmed.html")


class UnsubscribeView(View):
    def get(self, request, token):
        subscriber = get_object_or_404(Subscriber, token=token)
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["unsubscribed_at"])
        providers.sync_subscriber(subscriber)
        return render(request, "newsletter/unsubscribed.html")
