from django.urls import path

from compliance import views, views_audit

app_name = "compliance"

urlpatterns = [
    path("export/", views.DataExportView.as_view(), name="data_export"),
    path("delete/", views.AccountDeleteView.as_view(), name="account_delete"),
    path("access-log/", views_audit.AccessLogView.as_view(), name="access_log"),
]
