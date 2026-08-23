from django.urls import path

from apps.statistics import views

app_name = "statistics"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("map-data/", views.DashboardMapDataView.as_view(), name="map_data"),
    path("export/", views.KeyFigureExportView.as_view(), name="export"),
]
