from django.urls import path

from apps.inspections import views

app_name = "inspections"

urlpatterns = [
    path("", views.InspectionListView.as_view(), name="list"),
    path(
        "property/<int:property_pk>/new/",
        views.InspectionCreateView.as_view(),
        name="create",
    ),
]
