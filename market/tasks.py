from celery import shared_task

from core.http import HttpClient
from market.services import update_exchange_rates as load_exchange_rates


@shared_task
def update_exchange_rates() -> int:
    with HttpClient.from_settings() as http:
        return load_exchange_rates(http)
