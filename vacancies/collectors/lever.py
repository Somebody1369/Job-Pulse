from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final, override

from django.conf import settings

from core.http import HttpClient
from vacancies.collectors.ats import Board, mentions_location, parse_boards
from vacancies.collectors.base import Collector, VacancyData
from vacancies.collectors.html import html_to_text
from vacancies.salary import SalaryRange

LEVER_POSTINGS_URL: Final = "https://api.lever.co/v0/postings/{token}"
UKRAINE: Final = "UA"
REMOTE: Final = "remote"
MONTHS_PER_YEAR: Final = 12
SALARY_PERIODS: Final = {"per-month-salary": 1, "per-year-salary": MONTHS_PER_YEAR}


class LeverCollector(Collector):
    source_code = "lever"

    def __init__(
        self,
        http: HttpClient,
        *,
        boards: Sequence[Board] | None = None,
        keywords: Sequence[str] | None = None,
    ) -> None:
        super().__init__(http)
        self._boards = boards if boards is not None else parse_boards(settings.LEVER_BOARDS)
        self._keywords = keywords if keywords is not None else settings.ATS_LOCATION_KEYWORDS

    @override
    def collect(self, categories: Sequence[str]) -> list[VacancyData]:
        vacancies: list[VacancyData] = []
        for board in self._boards:
            url = LEVER_POSTINGS_URL.format(token=board.token)
            postings = self._http.get(url, params={"mode": "json"}).json()
            vacancies.extend(
                self.build(posting, board) for posting in postings if self._is_relevant(posting)
            )
        return vacancies

    def build(self, posting: dict[str, Any], board: Board) -> VacancyData:
        description_html = _description_html(posting)
        categories = posting.get("categories") or {}
        return VacancyData(
            external_id=posting["id"],
            url=posting["hostedUrl"],
            title=posting["text"].strip(),
            company=board.company or board.token,
            categories=frozenset(
                value for value in (categories.get("department"), categories.get("team")) if value
            ),
            locations=_locations(posting),
            is_remote=posting.get("workplaceType") == REMOTE,
            salary=_salary(posting.get("salaryRange")),
            description=html_to_text(description_html),
            description_html=description_html,
            published_at=datetime.fromtimestamp(posting["createdAt"] / 1000, tz=UTC),
        )

    def _is_relevant(self, posting: dict[str, Any]) -> bool:
        return (
            posting.get("country") == UKRAINE
            or posting.get("workplaceType") == REMOTE
            or mentions_location(_locations(posting), self._keywords)
        )


def _locations(posting: dict[str, Any]) -> tuple[str, ...]:
    categories = posting.get("categories") or {}
    names = categories.get("allLocations") or [categories.get("location")]
    return tuple(dict.fromkeys(name.strip() for name in names if name and name.strip()))


def _description_html(posting: dict[str, Any]) -> str:
    sections = [posting.get("description") or ""]
    for section in posting.get("lists") or []:
        sections.append(f"<h3>{section.get('text', '')}</h3><ul>{section.get('content', '')}</ul>")
    sections.append(posting.get("additional") or "")
    return "".join(sections)


def _salary(salary_range: dict[str, Any] | None) -> SalaryRange | None:
    if not salary_range:
        return None
    months = SALARY_PERIODS.get(salary_range.get("interval", ""))
    currency = str(salary_range.get("currency") or "").upper()
    if months is None or not currency:
        return None
    minimum, maximum = salary_range.get("min"), salary_range.get("max")
    return SalaryRange(
        minimum=round(minimum / months) if isinstance(minimum, int | float) else None,
        maximum=round(maximum / months) if isinstance(maximum, int | float) else None,
        currency=currency,
    )
