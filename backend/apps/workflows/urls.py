from django.urls import path

from apps.workflows import views

app_name = "workflows"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("new/", views.TaskCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="edit"),
    path("<int:pk>/complete/", views.TaskCompleteView.as_view(), name="complete"),
    path("<int:pk>/reopen/", views.TaskReopenView.as_view(), name="reopen"),
]
