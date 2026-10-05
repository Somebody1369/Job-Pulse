from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

admin.site.site_header = "JobPulse"
admin.site.site_title = "JobPulse"
admin.site.index_title = "Job market data"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
    path("admin/", admin.site.urls),
]
