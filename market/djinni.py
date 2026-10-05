import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from bs4 import BeautifulSoup, Tag

from core.http import HttpClient
from core.robots import UrlPolicy

DJINNI_SALARIES_URL: Final = "https://djinni.co/salaries/"
ALL_CATEGORIES: Final = ""
ALL_CATEGORIES_LABEL: Final = "All categories"
EXPECTED_SALARY_LABEL: Final = "середні очікування"
OFFERS_PER_CANDIDATE_LABEL: Final = "пропозицій в середньому"
OFFERED_SALARY_LABEL: Final = "середня вилка"
APPLICATIONS_PER_VACANCY_LABEL: Final = "відгуків в середньому"
PAIR_SIZE: Final = 2

_LEADING_INTEGER = re.compile(r"[+-]?\d+")


class MarketPageError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketStats:
    category: str
    category_label: str
    calculated_on: date
    active_candidates: int
    expected_min: int
    expected_max: int
    offers_per_candidate: Decimal
    vacancies_online: int
    vacancies_change: int | None
    offered_min: int
    offered_max: int
    applications_per_vacancy: Decimal
    djinni_index: Decimal | None
    offers_30d: int | None
    applications_30d: int | None


def parse_market_page(markup: bytes | str, category: str) -> MarketStats:
    soup = BeautifulSoup(markup, "lxml")
    label = _selected_category_label(soup)
    if (label == ALL_CATEGORIES_LABEL) != (category == ALL_CATEGORIES):
        raise MarketPageError(f"Djinni does not recognize the category {category!r}")
    candidates = _card(soup, "candidates_card")
    jobs = _card(soup, "jobs_card")
    candidate_rows = _rows(candidates)
    job_rows = _rows(jobs)
    expected_min, expected_max = _range(candidate_rows, EXPECTED_SALARY_LABEL)
    offered_min, offered_max = _range(job_rows, OFFERED_SALARY_LABEL)
    index_card = soup.select_one("#djinni_index_card")
    index_counts = _index_counts(index_card)
    return MarketStats(
        category=category,
        category_label=label,
        calculated_on=_calculated_on(candidates),
        active_candidates=_integer(_headline(candidates)),
        expected_min=expected_min,
        expected_max=expected_max,
        offers_per_candidate=_decimal(_row(candidate_rows, OFFERS_PER_CANDIDATE_LABEL)),
        vacancies_online=_integer(_headline(jobs)),
        vacancies_change=_optional_integer(jobs.select_one(".text-diff")),
        offered_min=offered_min,
        offered_max=offered_max,
        applications_per_vacancy=_decimal(_row(job_rows, APPLICATIONS_PER_VACANCY_LABEL)),
        djinni_index=_decimal(_headline(index_card)) if index_card else None,
        offers_30d=index_counts[0],
        applications_30d=index_counts[1],
    )


class DjinniMarketClient:
    def __init__(self, http: HttpClient, robots: UrlPolicy) -> None:
        self._http = http
        self._robots = robots

    def fetch(self, category: str) -> MarketStats:
        if not self._robots.is_allowed(DJINNI_SALARIES_URL):
            raise MarketPageError("robots.txt disallows the Djinni salaries page")
        params = {"category": category} if category else None
        response = self._http.get(DJINNI_SALARIES_URL, params=params)
        return parse_market_page(response.content, category)


def _selected_category_label(soup: BeautifulSoup) -> str:
    selected = soup.select_one("#filter_category option[selected]")
    if selected is None or not selected.get("value"):
        return ALL_CATEGORIES_LABEL
    return selected.get_text(strip=True)


def _card(soup: BeautifulSoup, card_id: str) -> Tag:
    card = soup.select_one(f"#{card_id}")
    if card is None:
        raise MarketPageError(f"Market page has no #{card_id}")
    return card


def _headline(card: Tag) -> Tag:
    value = card.select_one(".fs-1")
    if value is None:
        raise MarketPageError(f"#{card.get('id')} has no headline value")
    return value


def _rows(card: Tag) -> dict[str, Tag]:
    rows: dict[str, Tag] = {}
    for row in card.select(".row"):
        label = row.select_one(".text-secondary")
        value = row.select_one(".col-auto small")
        if label is not None and value is not None:
            rows[label.get_text(strip=True).casefold()] = value
    return rows


def _row(rows: dict[str, Tag], label: str) -> Tag:
    try:
        return rows[label]
    except KeyError as exc:
        raise MarketPageError(f"Market page has no {label!r} row") from exc


def _range(rows: dict[str, Tag], label: str) -> tuple[int, int]:
    bounds = [_integer(node) for node in _row(rows, label).select('[data-format="int"]')]
    if len(bounds) != PAIR_SIZE:
        raise MarketPageError(f"{label!r} is not a salary range")
    return bounds[0], bounds[1]


def _calculated_on(card: Tag) -> date:
    value = card.get("data-calculated-at")
    if not isinstance(value, str):
        raise MarketPageError("Market card has no calculation date")
    return datetime.fromisoformat(value).date()


def _index_counts(card: Tag | None) -> tuple[int | None, int | None]:
    if card is None:
        return None, None
    counts = [_optional_integer(node) for node in card.select('small[data-format="int"]')]
    return (counts[0], counts[1]) if len(counts) == PAIR_SIZE else (None, None)


def _integer(node: Tag) -> int:
    number = _optional_integer(node)
    if number is None:
        raise MarketPageError(f"Expected a number, got {node.get_text(strip=True)!r}")
    return number


def _optional_integer(node: Tag | None) -> int | None:
    if node is None:
        return None
    match = _LEADING_INTEGER.search("".join(node.get_text().split()))
    return int(match.group()) if match else None


def _decimal(node: Tag) -> Decimal:
    text = node.get_text(strip=True).lstrip("↑↓")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise MarketPageError(f"Expected a decimal, got {text!r}") from exc
