from celery import shared_task
from django.conf import settings

from core.http import HttpClient
from market.services import capture_market_snapshots as capture_snapshots
from market.services import update_exchange_rates as load_exchange_rates


@shared_task
def update_exchange_rates() -> int:
    with HttpClient.from_settings() as http:
        return load_exchange_rates(http)


@shared_task
def capture_market_snapshots() -> dict[str, int]:
    with HttpClient.from_settings() as http:
        result = capture_snapshots(http, settings.MARKET_CATEGORIES)
    return {"captured": len(result.captured), "failed": len(result.failed)}
