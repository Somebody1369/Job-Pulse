from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Self

from core.http import HttpClient
from market.models import ExchangeRate
from market.nbu import NbuClient

BASE_CURRENCY: Final = "UAH"
TARGET_CURRENCY: Final = "USD"


def update_exchange_rates(http: HttpClient, on: date | None = None) -> int:
    rates = NbuClient(http).fetch_rates(on)
    ExchangeRate.objects.bulk_create(
        [
            ExchangeRate(
                currency=rate.currency,
                rate_date=rate.rate_date,
                uah_per_unit=rate.uah_per_unit,
            )
            for rate in rates
        ],
        update_conflicts=True,
        unique_fields=("currency", "rate_date"),
        update_fields=("uah_per_unit", "updated_at"),
    )
    return len(rates)


class UsdConverter:
    def __init__(self, uah_per_unit: Mapping[str, Decimal]) -> None:
        self._uah_per_unit = {BASE_CURRENCY: Decimal(1), **uah_per_unit}

    @classmethod
    def from_latest_rates(cls) -> Self:
        latest = ExchangeRate.objects.order_by("currency", "-rate_date").distinct("currency")
        return cls({rate.currency: rate.uah_per_unit for rate in latest})

    def convert(self, amount: int | None, currency: str) -> int | None:
        if amount is None:
            return None
        if currency == TARGET_CURRENCY:
            return amount
        source_rate = self._uah_per_unit.get(currency)
        target_rate = self._uah_per_unit.get(TARGET_CURRENCY)
        if source_rate is None or target_rate is None:
            return None
        usd = Decimal(amount) * source_rate / target_rate
        return int(usd.quantize(Decimal(1), rounding=ROUND_HALF_UP))
