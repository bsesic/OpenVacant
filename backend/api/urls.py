from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api import views

app_name = "api"

router = DefaultRouter()
router.register("organizations", views.OrganizationViewSet, basename="organization")
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path("users/me/", views.MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
