from django.urls import path

from apps.properties import views

app_name = "properties"

urlpatterns = [
    path("", views.PropertyListView.as_view(), name="list"),
    path("new/", views.PropertyCreateView.as_view(), name="create"),
    path("parcels/", views.ParcelListView.as_view(), name="parcels"),
    path("<int:pk>/", views.PropertyDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PropertyUpdateView.as_view(), name="edit"),
    path("<int:pk>/history/", views.PropertyHistoryView.as_view(), name="history"),
    path("<int:pk>/status/", views.PropertyTransitionView.as_view(), name="transition"),
    path("<int:pk>/occupancy/", views.PropertyVacancyStatusView.as_view(), name="occupancy"),
    path("<int:pk>/publication/", views.PropertyPublicationView.as_view(), name="publication"),
    path("<int:pk>/damages/", views.PropertyDamageCreateView.as_view(), name="damage_create"),
    path(
        "<int:pk>/damages/<int:damage_pk>/delete/",
        views.PropertyDamageDeleteView.as_view(),
        name="damage_delete",
    ),
]
