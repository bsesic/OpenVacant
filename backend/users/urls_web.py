from django.urls import path

from users.views import ProfileUpdateView, ProfileView

urlpatterns = [
    path("", ProfileView.as_view(), name="profile"),
    path("edit/", ProfileUpdateView.as_view(), name="profile_edit"),
]
