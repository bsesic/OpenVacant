from django.urls import path

from apps.heritage import views

app_name = "heritage"

urlpatterns = [
    path("", views.MonumentListView.as_view(), name="monuments"),
    path("new/", views.MonumentCreateView.as_view(), name="monument_create"),
    path("<int:pk>/edit/", views.MonumentUpdateView.as_view(), name="monument_edit"),
    path(
        "property/<int:property_pk>/check/",
        views.HeritageCheckCreateView.as_view(),
        name="check_create",
    ),
]
