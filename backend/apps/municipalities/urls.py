from django.urls import path

from apps.municipalities import views

app_name = "municipalities"

urlpatterns = [
    path("settings/", views.MunicipalitySettingsView.as_view(), name="settings"),
    path("modules/", views.ModuleSettingsView.as_view(), name="modules"),
    path("districts/", views.DistrictListView.as_view(), name="districts"),
    path("districts/new/", views.DistrictCreateView.as_view(), name="district_create"),
    path("districts/<int:pk>/edit/", views.DistrictUpdateView.as_view(), name="district_edit"),
    path(
        "districts/<int:pk>/delete/",
        views.DistrictDeleteView.as_view(),
        name="district_delete",
    ),
    path("<int:pk>/", views.MunicipalityDetailView.as_view(), name="detail"),
]
