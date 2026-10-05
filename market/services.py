import logging
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Self

import requests
from django.conf import settings
from django.db import transaction

from core.http import HttpClient
from core.robots import RobotsPolicy
from market.djinni import DjinniMarketClient, MarketPageError
from market.models import ExchangeRate, MarketSnapshot, SalaryResponse, SalarySurvey
from market.nbu import NbuClient
from market.surveys import (
    SURVEY_URL_TEMPLATE,
    SurveyResponse,
    decode_survey,
    parse_survey,
    survey_period,
)

BASE_CURRENCY: Final = "UAH"
TARGET_CURRENCY: Final = "USD"
SURVEY_BATCH_SIZE: Final = 2000

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    captured: list[MarketSnapshot]
    failed: list[str]


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


def capture_market_snapshots(http: HttpClient, categories: Iterable[str]) -> SnapshotResult:
    client = DjinniMarketClient(http, RobotsPolicy(http, settings.SCRAPER_USER_AGENT))
    captured: list[MarketSnapshot] = []
    failed: list[str] = []
    for category in categories:
        try:
            stats = client.fetch(category)
        except (requests.RequestException, MarketPageError) as exc:
            logger.warning("Failed to capture the %r market snapshot: %s", category, exc)
            failed.append(category)
            continue
        fields = asdict(stats)
        snapshot, _ = MarketSnapshot.objects.update_or_create(
            category=fields.pop("category"),
            calculated_on=fields.pop("calculated_on"),
            defaults=fields,
        )
        captured.append(snapshot)
    return SnapshotResult(captured=captured, failed=failed)


def import_salary_survey(http: HttpClient, name: str) -> SalarySurvey:
    period = survey_period(name)
    url = SURVEY_URL_TEMPLATE.format(name=name)
    responses = list(parse_survey(decode_survey(http.get(url).content)))
    return _store_survey(name, period, url, responses)


@transaction.atomic
def _store_survey(
    name: str, period: date, url: str, responses: list[SurveyResponse]
) -> SalarySurvey:
    survey, _ = SalarySurvey.objects.update_or_create(
        name=name,
        defaults={"period": period, "source_url": url, "response_count": len(responses)},
    )
    survey.responses.all().delete()
    SalaryResponse.objects.bulk_create(
        [SalaryResponse(survey=survey, **asdict(response)) for response in responses],
        batch_size=SURVEY_BATCH_SIZE,
    )
    return survey
