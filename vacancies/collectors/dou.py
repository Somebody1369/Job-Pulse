import re
from dataclasses import dataclass
from typing import Final, override
from urllib.parse import urlsplit, urlunsplit

from vacancies.collectors.base import RssCollector, VacancyData
from vacancies.collectors.html import html_to_text
from vacancies.collectors.rss import FeedFormatError, FeedItem

COMPANY_SEPARATOR: Final = " в "
DETAILS_SEPARATOR: Final = ", "
REMOTE_MARKER: Final = "віддалено"
REPLY_LINK_SELECTOR: Final = 'a[href$="#reply-btn-id"]'

_VACANCY_ID = re.compile(r"/vacancies/(?P<id>\d+)/")
_CURRENCY = re.compile(r"[$€₴]|грн", re.IGNORECASE)


@dataclass(frozen=True, slots=True, kw_only=True)
class DouTitle:
    position: str
    company: str = ""
    locations: tuple[str, ...] = ()
    salary_text: str = ""
    is_remote: bool = False


def parse_title(raw: str) -> DouTitle:
    position, separator, rest = raw.rpartition(COMPANY_SEPARATOR)
    if not separator:
        return DouTitle(position=raw.strip())
    company, *details = (part.strip() for part in rest.split(DETAILS_SEPARATOR))
    salary_text = next((part for part in details if _is_salary(part)), "")
    is_remote = any(_is_remote(part) for part in details)
    locations = tuple(
        part for part in details if part and part != salary_text and not _is_remote(part)
    )
    return DouTitle(
        position=position.strip(),
        company=company,
        locations=locations,
        salary_text=salary_text,
        is_remote=is_remote,
    )


def _is_salary(part: str) -> bool:
    return any(char.isdigit() for char in part) and _CURRENCY.search(part) is not None


def _is_remote(part: str) -> bool:
    return part.casefold() == REMOTE_MARKER


class DouCollector(RssCollector):
    source_code = "dou"
    feed_url = "https://jobs.dou.ua/vacancies/feeds/"

    @override
    def feed_params(self, category: str) -> dict[str, str]:
        return {"category": category}

    @override
    def build(self, item: FeedItem, category: str) -> VacancyData:
        title = parse_title(item.title)
        return VacancyData(
            external_id=self._external_id(item.link),
            url=self._canonical_url(item.link),
            title=title.position,
            company=title.company,
            categories=frozenset({category, *item.categories}),
            locations=title.locations,
            is_remote=title.is_remote,
            salary_text=title.salary_text,
            description=html_to_text(item.description_html, exclude=REPLY_LINK_SELECTOR),
            description_html=item.description_html,
            published_at=item.published_at,
        )

    @staticmethod
    def _external_id(link: str) -> str:
        match = _VACANCY_ID.search(link)
        if match is None:
            raise FeedFormatError(f"Unexpected DOU vacancy link: {link}")
        return match["id"]

    @staticmethod
    def _canonical_url(link: str) -> str:
        scheme, netloc, path, _, _ = urlsplit(link)
        return urlunsplit((scheme, netloc, path, "", ""))
