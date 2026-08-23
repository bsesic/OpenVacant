from django.urls import path

from apps.integrations import views

app_name = "integrations"

urlpatterns = [
    path("", views.ApiClientListView.as_view(), name="clients"),
    path("new/", views.ApiClientCreateView.as_view(), name="client_create"),
    path("<int:pk>/edit/", views.ApiClientUpdateView.as_view(), name="client_edit"),
    path("<int:pk>/revoke/", views.ApiClientRevokeView.as_view(), name="client_revoke"),
    path(
        "<int:pk>/reactivate/",
        views.ApiClientReactivateView.as_view(),
        name="client_reactivate",
    ),
    path("<int:pk>/rotate/", views.ApiClientRotateKeyView.as_view(), name="client_rotate"),
]
