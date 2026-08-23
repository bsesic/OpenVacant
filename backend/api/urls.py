"""API v1.

Four separated areas. Public data and internal professional data are kept apart
at the routing level, not only by permission checks, so that reading the URL map
already tells you which endpoints could ever expose case data.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api import administration, citizen, integration, public, views

app_name = "api"

public_router = DefaultRouter()
public_router.register("properties", public.PublicPropertyViewSet, basename="public-property")

citizen_router = DefaultRouter()
citizen_router.register("reports", citizen.ReportViewSet, basename="citizen-report")

admin_router = DefaultRouter()
admin_router.register("properties", administration.AdminPropertyViewSet, basename="property")
admin_router.register("reports", administration.AdminReportViewSet, basename="report")
admin_router.register(
    "inspections", administration.AdminInspectionViewSet, basename="inspection"
)
admin_router.register("tasks", administration.AdminTaskViewSet, basename="task")

integration_router = DefaultRouter()
integration_router.register("geodata-layers", integration.GeoLayerViewSet, basename="geolayer")

public_patterns = [
    path("municipality/", public.PublicMunicipalityView.as_view(), name="municipality"),
    path("statistics/", public.PublicStatisticsView.as_view(), name="statistics"),
    path("", include(public_router.urls)),
]

citizen_patterns = [
    path("", include(citizen_router.urls)),
]

admin_patterns = [
    path("statistics/", administration.AdminStatisticsView.as_view(), name="statistics"),
    path("", include(admin_router.urls)),
]

integration_patterns = [
    path("client/", integration.ApiClientSelfView.as_view(), name="client"),
    path("", include(integration_router.urls)),
]

account_router = DefaultRouter()
account_router.register(
    "organizations", views.OrganizationViewSet, basename="organization"
)
account_router.register(
    "notifications", views.NotificationViewSet, basename="notification"
)

urlpatterns = [
    path("users/me/", views.MeView.as_view(), name="me"),
    path("public/", include((public_patterns, "public"), namespace="public")),
    path("citizen/", include((citizen_patterns, "citizen"), namespace="citizen")),
    path("admin/", include((admin_patterns, "administration"), namespace="administration")),
    path(
        "integration/",
        include((integration_patterns, "integration"), namespace="integration"),
    ),
    path("", include(account_router.urls)),
]
