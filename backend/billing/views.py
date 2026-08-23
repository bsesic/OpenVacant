from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from billing import services, webhooks
from billing.models import BillingAccount, ProcessedStripeEvent


def _get_account(organization):
    account, _created = BillingAccount.objects.get_or_create(organization=organization)
    return account


class BillingManagerMixin(LoginRequiredMixin):
    """Require an active organization the user can manage."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        org = getattr(request, "organization", None)
        if org is None or not org.can_manage(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class PricingView(TemplateView):
    template_name = "billing/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plans"] = settings.STRIPE_PLANS
        context["billing_enabled"] = settings.BILLING_ENABLED
        return context


class BillingView(BillingManagerMixin, TemplateView):
    template_name = "billing/billing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = _get_account(self.request.organization)
        context["plans"] = settings.STRIPE_PLANS
        context["billing_enabled"] = settings.BILLING_ENABLED
        return context


class CheckoutView(BillingManagerMixin, View):
    def post(self, request):
        if not settings.BILLING_ENABLED:
            messages.error(request, _("Billing is not configured."))
            return redirect("billing:pricing")
        plan_key = request.POST.get("plan")
        price_id = next((p["price_id"] for p in settings.STRIPE_PLANS if p["key"] == plan_key), "")
        if not price_id:
            messages.error(request, _("Unknown plan."))
            return redirect("billing:pricing")
        account = _get_account(request.organization)
        session = services.create_checkout_session(
            account,
            price_id,
            success_url=request.build_absolute_uri(reverse("billing:success")),
            cancel_url=request.build_absolute_uri(reverse("billing:cancel")),
        )
        return redirect(session["url"])


class PortalView(BillingManagerMixin, View):
    def post(self, request):
        account = _get_account(request.organization)
        if not settings.BILLING_ENABLED or not account.stripe_customer_id:
            messages.error(request, _("No billing account yet."))
            return redirect("billing:billing")
        session = services.create_portal_session(
            account, return_url=request.build_absolute_uri(reverse("billing:billing"))
        )
        return redirect(session["url"])


class SuccessView(BillingManagerMixin, TemplateView):
    template_name = "billing/success.html"


class CancelView(BillingManagerMixin, TemplateView):
    template_name = "billing/cancel.html"


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = services.construct_event(payload, sig_header)
        except Exception:
            return HttpResponseBadRequest("Invalid payload or signature")

        _processed, created = ProcessedStripeEvent.objects.get_or_create(
            event_id=event["id"], defaults={"event_type": event.get("type", "")}
        )
        if created:
            webhooks.handle_event(event)
        return HttpResponse(status=200)
