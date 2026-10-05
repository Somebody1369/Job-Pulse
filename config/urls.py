from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "JobPulse"
admin.site.site_title = "JobPulse"
admin.site.index_title = "Job market data"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="analytics:dashboard", permanent=False)),
    path("analytics/", include("analytics.urls")),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
]
