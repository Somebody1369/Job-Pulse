from django.urls import path, re_path

from analytics.views import DashboardView, export_table

app_name = "analytics"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    re_path(r"^export/(?P<name>[a-z]+)\.(?P<extension>csv|xlsx)$", export_table, name="export"),
]
