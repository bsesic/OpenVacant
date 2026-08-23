from django.urls import path

from billing import views

app_name = "billing"

urlpatterns = [
    path("pricing/", views.PricingView.as_view(), name="pricing"),
    path("", views.BillingView.as_view(), name="billing"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("portal/", views.PortalView.as_view(), name="portal"),
    path("success/", views.SuccessView.as_view(), name="success"),
    path("cancel/", views.CancelView.as_view(), name="cancel"),
    path("webhook/", views.StripeWebhookView.as_view(), name="webhook"),
]
