from django.urls import path

from newsletter import views

app_name = "newsletter"

urlpatterns = [
    path("", views.SubscribeView.as_view(), name="subscribe"),
    path("confirm/<str:token>/", views.ConfirmView.as_view(), name="confirm"),
    path("unsubscribe/<str:token>/", views.UnsubscribeView.as_view(), name="unsubscribe"),
]
