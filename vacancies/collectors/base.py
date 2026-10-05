from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, override

from core.http import HttpClient
from vacancies.collectors.rss import FeedItem, parse_feed
from vacancies.salary import SalaryRange


@dataclass(frozen=True, slots=True, kw_only=True)
class VacancyData:
    external_id: str
    url: str
    title: str
    published_at: datetime
    company: str = ""
    categories: frozenset[str] = frozenset()
    locations: tuple[str, ...] = ()
    is_remote: bool | None = None
    salary_text: str = ""
    salary: SalaryRange | None = None
    description: str = ""
    description_html: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class VacancyDetails:
    company: str = ""
    company_website: str = ""
    locations: tuple[str, ...] = ()
    is_remote: bool | None = None
    salary: SalaryRange | None = None
    experience_months: int | None = None
    english_level: str = ""


class DetailsParseError(ValueError):
    pass


class Collector(ABC):
    source_code: ClassVar[str]

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @abstractmethod
    def collect(self, category: str) -> list[VacancyData]: ...


class RssCollector(Collector):
    feed_url: ClassVar[str]

    @override
    def collect(self, category: str) -> list[VacancyData]:
        response = self._http.get(self.feed_url, params=self.feed_params(category))
        return [self.build(item, category) for item in parse_feed(response.content)]

    @abstractmethod
    def feed_params(self, category: str) -> dict[str, str]: ...

    @abstractmethod
    def build(self, item: FeedItem, category: str) -> VacancyData: ...


class DetailsCollector(ABC):
    @abstractmethod
    def fetch_details(self, url: str) -> VacancyDetails: ...
