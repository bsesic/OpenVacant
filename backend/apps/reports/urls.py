from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    # Citizen surface
    path("new/", views.ReportCreateView.as_view(), name="create"),
    path("submitted/<str:reference>/", views.ReportSubmittedView.as_view(), name="submitted"),
    path("mine/", views.MyReportsView.as_view(), name="mine"),
    path("map/", views.PublicMapView.as_view(), name="map"),
    path("map/data/", views.PublicMapDataView.as_view(), name="map_data"),
    # Administration surface
    path("", views.ReportListView.as_view(), name="list"),
    path("<int:pk>/", views.ReportDetailView.as_view(), name="detail"),
    path("<int:pk>/moderate/", views.ReportModerateView.as_view(), name="moderate"),
    path("<int:pk>/accept/", views.ReportAcceptView.as_view(), name="accept"),
    path("<int:pk>/attach/", views.ReportAttachView.as_view(), name="attach"),
    path(
        "<int:pk>/photos/<int:photo_pk>/publication/",
        views.ReportPhotoPublicationView.as_view(),
        name="photo_publication",
    ),
]
