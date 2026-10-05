from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final

from core.http import HttpClient

NBU_EXCHANGE_URL: Final = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
NBU_DATE_FORMAT: Final = "%d.%m.%Y"


class NbuResponseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Rate:
    currency: str
    rate_date: date
    uah_per_unit: Decimal


class NbuClient:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def fetch_rates(self, on: date | None = None) -> list[Rate]:
        params = {"json": ""}
        if on is not None:
            params["date"] = on.strftime("%Y%m%d")
        payload = self._http.get(NBU_EXCHANGE_URL, params=params).json(parse_float=Decimal)
        if not isinstance(payload, list):
            raise NbuResponseError(f"Expected a list of rates, got {type(payload).__name__}")
        return [self._parse(entry) for entry in payload]

    @staticmethod
    def _parse(entry: dict[str, Any]) -> Rate:
        try:
            return Rate(
                currency=str(entry["cc"]).upper(),
                rate_date=datetime.strptime(entry["exchangedate"], NBU_DATE_FORMAT).date(),
                uah_per_unit=Decimal(entry["rate"]),
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise NbuResponseError(f"Malformed NBU rate entry: {entry!r}") from exc
