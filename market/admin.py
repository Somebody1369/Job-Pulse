from django.contrib import admin

from market.models import ExchangeRate, MarketSnapshot


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin[ExchangeRate]):
    list_display = ("currency", "rate_date", "uah_per_unit", "updated_at")
    list_filter = ("currency",)
    search_fields = ("currency",)
    date_hierarchy = "rate_date"


@admin.register(MarketSnapshot)
class MarketSnapshotAdmin(admin.ModelAdmin[MarketSnapshot]):
    list_display = (
        "category_label",
        "calculated_on",
        "active_candidates",
        "vacancies_online",
        "candidates_per_vacancy",
        "expected_min",
        "expected_max",
        "offered_min",
        "offered_max",
        "applications_per_vacancy",
        "djinni_index",
    )
    list_filter = ("category_label",)
    date_hierarchy = "calculated_on"
