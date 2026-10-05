import re
import unicodedata
from dataclasses import dataclass
from typing import Final

CURRENCY_MARKERS: Final = (
    ("$", "USD"),
    ("usd", "USD"),
    ("€", "EUR"),
    ("eur", "EUR"),
    ("₴", "UAH"),
    ("грн", "UAH"),
    ("uah", "UAH"),
)
LOWER_BOUND_MARKERS: Final = ("від", "from")
UPPER_BOUND_MARKERS: Final = ("до", "up to")
THOUSANDS_SUFFIXES: Final = frozenset({"k", "к"})

_AMOUNT = re.compile(r"(?P<digits>\d{1,3}(?: \d{3})+|\d+)(?:\s*(?P<suffix>[kк])\b)?")


@dataclass(frozen=True, slots=True)
class SalaryRange:
    minimum: int | None
    maximum: int | None
    currency: str


NO_SALARY: Final = SalaryRange(minimum=None, maximum=None, currency="")


def parse_salary(text: str) -> SalaryRange | None:
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    currency = _detect_currency(normalized)
    matches = list(_AMOUNT.finditer(normalized))
    if currency is None or not matches:
        return None
    multiplier = 1000 if any(match["suffix"] in THOUSANDS_SUFFIXES for match in matches) else 1
    amounts = sorted(int(match["digits"].replace(" ", "")) * multiplier for match in matches)
    if len(amounts) > 1:
        return SalaryRange(minimum=amounts[0], maximum=amounts[-1], currency=currency)
    (amount,) = amounts
    if normalized.startswith(UPPER_BOUND_MARKERS):
        return SalaryRange(minimum=None, maximum=amount, currency=currency)
    if normalized.startswith(LOWER_BOUND_MARKERS):
        return SalaryRange(minimum=amount, maximum=None, currency=currency)
    return SalaryRange(minimum=amount, maximum=amount, currency=currency)


def format_salary_range(minimum: int | None, maximum: int | None) -> str:
    if minimum is None and maximum is None:
        return "—"
    if maximum is None:
        return f"from {minimum}"
    if minimum is None:
        return f"up to {maximum}"
    if minimum == maximum:
        return str(minimum)
    return f"{minimum}–{maximum}"


def _detect_currency(text: str) -> str | None:
    return next((code for marker, code in CURRENCY_MARKERS if marker in text), None)
