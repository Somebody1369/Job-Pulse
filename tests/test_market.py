from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
import responses
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from responses import matchers

from core.http import HttpClient
from market.models import ExchangeRate
from market.nbu import NBU_EXCHANGE_URL, NbuClient, NbuResponseError, Rate
from market.services import UsdConverter, update_exchange_rates

RATE_DATE = date(2026, 10, 2)


def nbu_payload(usd: float = 44.8333) -> list[dict[str, Any]]:
    return [
        {"r030": 840, "txt": "Долар США", "rate": usd, "cc": "USD", "exchangedate": "02.10.2026"},
        {"r030": 978, "txt": "Євро", "rate": 50.6975, "cc": "EUR", "exchangedate": "02.10.2026"},
    ]


def mock_nbu(mock: responses.RequestsMock, payload: object, **params: str) -> None:
    mock.get(
        NBU_EXCHANGE_URL,
        json=payload,
        match=[matchers.query_param_matcher({"json": "", **params})],
    )


def test_fetch_rates_parses_payload(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mock_nbu(mocked_responses, nbu_payload(), date="20261002")

    rates = NbuClient(http_client).fetch_rates(RATE_DATE)

    assert rates == [
        Rate(currency="USD", rate_date=RATE_DATE, uah_per_unit=Decimal("44.8333")),
        Rate(currency="EUR", rate_date=RATE_DATE, uah_per_unit=Decimal("50.6975")),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "service unavailable"},
        [{"rate": 44.8, "exchangedate": "02.10.2026"}],
        [{"cc": "USD", "rate": 44.8, "exchangedate": "2026-10-02"}],
    ],
)
def test_fetch_rates_rejects_malformed_payload(
    http_client: HttpClient, mocked_responses: responses.RequestsMock, payload: object
) -> None:
    mock_nbu(mocked_responses, payload)

    with pytest.raises(NbuResponseError):
        NbuClient(http_client).fetch_rates()


@pytest.mark.django_db
def test_update_exchange_rates_upserts_rates(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mock_nbu(mocked_responses, nbu_payload(usd=44.0), date="20261002")
    update_exchange_rates(http_client, RATE_DATE)
    mocked_responses.replace(
        responses.GET,
        NBU_EXCHANGE_URL,
        json=nbu_payload(usd=45.5),
        match=[matchers.query_param_matcher({"json": "", "date": "20261002"})],
    )

    assert update_exchange_rates(http_client, RATE_DATE) == 2

    assert ExchangeRate.objects.count() == 2
    assert ExchangeRate.objects.get(currency="USD").uah_per_unit == Decimal("45.5")


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        (None, "UAH", None),
        (2500, "USD", 2500),
        (40000, "UAH", 1000),
        (1000, "EUR", 1100),
        (1, "EUR", 1),
        (1000, "PLN", None),
    ],
)
def test_usd_converter(amount: int | None, currency: str, expected: int | None) -> None:
    converter = UsdConverter({"USD": Decimal("40"), "EUR": Decimal("44")})

    assert converter.convert(amount, currency) == expected


def test_usd_converter_without_usd_rate() -> None:
    assert UsdConverter({}).convert(1000, "UAH") is None


@pytest.mark.django_db
def test_usd_converter_uses_latest_rates() -> None:
    ExchangeRate.objects.bulk_create(
        [
            ExchangeRate(currency="USD", rate_date=date(2026, 10, 1), uah_per_unit=Decimal("20")),
            ExchangeRate(currency="USD", rate_date=RATE_DATE, uah_per_unit=Decimal("40")),
        ]
    )

    assert UsdConverter.from_latest_rates().convert(40000, "UAH") == 1000


@pytest.mark.django_db
def test_update_exchange_rates_command(mocked_responses: responses.RequestsMock) -> None:
    mock_nbu(mocked_responses, nbu_payload(), date="20261002")
    output = StringIO()

    call_command("update_exchange_rates", "--date", "2026-10-02", stdout=output)

    assert "Stored 2 exchange rates" in output.getvalue()
    assert str(ExchangeRate.objects.get(currency="EUR")) == "EUR 50.697500 UAH on 2026-10-02"


@pytest.mark.django_db
def test_exchange_rate_admin_renders(admin_client: Client) -> None:
    response = admin_client.get(reverse("admin:market_exchangerate_changelist"))

    assert response.status_code == 200
