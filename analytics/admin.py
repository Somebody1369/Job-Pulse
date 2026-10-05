from typing import override

from django.contrib import admin
from django.http import HttpRequest

from analytics.models import DashboardReport


@admin.register(DashboardReport)
class DashboardReportAdmin(admin.ModelAdmin[DashboardReport]):
    list_display = ("created_at",)
    exclude = ("image",)
    readonly_fields = ("created_at",)

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
