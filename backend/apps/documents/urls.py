from django.urls import path

from apps.documents import views

app_name = "documents"

urlpatterns = [
    path("", views.DocumentListView.as_view(), name="list"),
    path(
        "property/<int:property_pk>/upload/",
        views.DocumentCreateView.as_view(),
        name="create",
    ),
    path("<int:pk>/visibility/", views.DocumentVisibilityView.as_view(), name="visibility"),
    path("<int:pk>/delete/", views.DocumentDeleteView.as_view(), name="delete"),
]
