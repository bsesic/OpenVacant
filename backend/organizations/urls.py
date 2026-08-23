from django.urls import path

from organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.OrganizationListView.as_view(), name="list"),
    path("create/", views.OrganizationCreateView.as_view(), name="create"),
    path("switch/<int:pk>/", views.SwitchOrganizationView.as_view(), name="switch"),
    path(
        "invitations/accept/<str:token>/",
        views.AcceptInvitationView.as_view(),
        name="accept_invitation",
    ),
    path("<slug:slug>/", views.OrganizationDetailView.as_view(), name="detail"),
    path("<slug:slug>/invite/", views.InvitationCreateView.as_view(), name="invite"),
    path(
        "<slug:slug>/members/<int:pk>/remove/",
        views.RemoveMembershipView.as_view(),
        name="remove_member",
    ),
]
