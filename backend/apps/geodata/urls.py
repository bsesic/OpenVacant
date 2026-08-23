from django.urls import path

from apps.geodata import views

app_name = "geodata"

urlpatterns = [
    path("layers/", views.GeoLayerListView.as_view(), name="layers"),
    path("address-search/", views.AddressSearchView.as_view(), name="address_search"),
]
