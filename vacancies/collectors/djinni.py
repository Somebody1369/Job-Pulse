import re
from typing import override

from vacancies.collectors.base import RssCollector, VacancyData
from vacancies.collectors.html import html_to_text
from vacancies.collectors.rss import FeedFormatError, FeedItem

_JOB_ID = re.compile(r"/jobs/(?P<id>\d+)-")


class DjinniCollector(RssCollector):
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

    @staticmethod
    def _external_id(link: str) -> str:
        match = _JOB_ID.search(link)
        if match is None:
            raise FeedFormatError(f"Unexpected Djinni job link: {link}")
        return match["id"]
