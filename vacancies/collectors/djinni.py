import re
from dataclasses import replace
from typing import Final, override

from bs4 import BeautifulSoup

from vacancies.collectors.base import (
    DetailsCollector,
    DetailsParseError,
    RssCollector,
    VacancyData,
    VacancyDetails,
)
from vacancies.collectors.html import html_to_text
from vacancies.collectors.jsonld import details_from_job_posting, find_job_posting
from vacancies.collectors.rss import FeedFormatError, FeedItem

ENGLISH_LABELS: Final = frozenset({"англійська", "english"})

_JOB_ID = re.compile(r"/jobs/(?P<id>\d+)-")
_CEFR_LEVEL = re.compile(r"\b(?P<level>[ABC][12])\b")


def parse_job_page(markup: bytes | str) -> VacancyDetails:
    soup = BeautifulSoup(markup, "lxml")
    posting = find_job_posting(soup)
    if posting is None:
        raise DetailsParseError("Job page has no JobPosting structured data")
    return replace(details_from_job_posting(posting), english_level=_english_level(soup))


def _english_level(soup: BeautifulSoup) -> str:
    for row in soup.select(".detail-rows__line"):
        name = row.select_one(".detail-rows__name")
        value = row.select_one(".detail-rows__value")
        if name is None or value is None:
            continue
        if name.get_text(strip=True).casefold() in ENGLISH_LABELS:
            match = _CEFR_LEVEL.search(value.get_text())
            return match["level"] if match else ""
    return ""


class DjinniCollector(RssCollector, DetailsCollector):
    source_code = "djinni"
    feed_url = "https://djinni.co/jobs/rss/"

    @override
    def feed_params(self, category: str) -> dict[str, str]:
        return {"primary_keyword": category}

    @override
    def build(self, item: FeedItem, category: str) -> VacancyData:
        return VacancyData(
            external_id=self._external_id(item.link),
            url=item.link,
            title=item.title,
            categories=frozenset(item.categories or (category,)),
            description=html_to_text(item.description_html),
            description_html=item.description_html,
            published_at=item.published_at,
        )

    @override
    def fetch_details(self, url: str) -> VacancyDetails:
        return parse_job_page(self._http.get(url).content)

    @staticmethod
    def _external_id(link: str) -> str:
        match = _JOB_ID.search(link)
        if match is None:
            raise FeedFormatError(f"Unexpected Djinni job link: {link}")
        return match["id"]
