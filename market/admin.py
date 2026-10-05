from django.contrib import admin

from market.models import ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin[ExchangeRate]):
    list_display = ("currency", "rate_date", "uah_per_unit", "updated_at")
    list_filter = ("currency",)
    search_fields = ("currency",)
    date_hierarchy = "rate_date"
