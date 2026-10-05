import html
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final, override

from django.conf import settings

from core.http import HttpClient
from vacancies.collectors.ats import Board, mentions_location, parse_boards
from vacancies.collectors.base import Collector, VacancyData
from vacancies.collectors.html import html_to_text

GREENHOUSE_JOBS_URL: Final = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
REMOTE_MARKER: Final = "remote"


class GreenhouseCollector(Collector):
    source_code = "greenhouse"

    def __init__(
        self,
        http: HttpClient,
        *,
        boards: Sequence[Board] | None = None,
        keywords: Sequence[str] | None = None,
    ) -> None:
        super().__init__(http)
        self._boards = boards if boards is not None else parse_boards(settings.GREENHOUSE_BOARDS)
        self._keywords = keywords if keywords is not None else settings.ATS_LOCATION_KEYWORDS

    @override
    def collect(self, categories: Sequence[str]) -> list[VacancyData]:
        vacancies: list[VacancyData] = []
        for board in self._boards:
            url = GREENHOUSE_JOBS_URL.format(token=board.token)
            jobs = self._http.get(url, params={"content": "true"}).json()["jobs"]
            vacancies.extend(self.build(job, board) for job in jobs if self._is_relevant(job))
        return vacancies

    def build(self, job: dict[str, Any], board: Board) -> VacancyData:
        description_html = html.unescape(job.get("content") or "")
        locations = _locations(job)
        return VacancyData(
            external_id=str(job["id"]),
            url=job["absolute_url"],
            title=job["title"].strip(),
            company=board.company or job.get("company_name") or "",
            categories=frozenset(
                department["name"]
                for department in job.get("departments", [])
                if department.get("name")
            ),
            locations=locations,
            is_remote=any(REMOTE_MARKER in location.casefold() for location in locations),
            description=html_to_text(description_html),
            description_html=description_html,
            published_at=datetime.fromisoformat(job.get("first_published") or job["updated_at"]),
        )

    def _is_relevant(self, job: dict[str, Any]) -> bool:
        return mentions_location(_locations(job), self._keywords)


def _locations(job: dict[str, Any]) -> tuple[str, ...]:
    names = [(job.get("location") or {}).get("name", "")]
    names.extend(office.get("name", "") for office in job.get("offices", []))
    return tuple(dict.fromkeys(name.strip() for name in names if name and name.strip()))
