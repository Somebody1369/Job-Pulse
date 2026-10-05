from datetime import UTC, datetime

import pytest
import responses
from responses import matchers

from core.http import HttpClient
from tests.utils import DJINNI_FEED_URL, read_fixture
from vacancies.collectors.djinni import DjinniCollector
from vacancies.collectors.rss import FeedFormatError, FeedItem


def make_item(*, link: str, categories: tuple[str, ...] = ()) -> FeedItem:
    return FeedItem(
        title="Golang Engineer",
        link=link,
        description_html="<p>Go and Kafka</p>",
        published_at=datetime(2026, 10, 1, tzinfo=UTC),
        categories=categories,
    )


def test_collect_builds_vacancies_from_feed(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        DJINNI_FEED_URL,
        body=read_fixture("djinni_python.xml"),
        match=[matchers.query_param_matcher({"primary_keyword": "Python"})],
    )

    vacancies = DjinniCollector(http_client).collect("Python")

    assert [vacancy.external_id for vacancy in vacancies] == ["851542", "851515", "829608"]
    vacancy = vacancies[1]
    assert vacancy.title == "Senior Software Engineer (Go, Python)"
    assert vacancy.url == "https://djinni.co/jobs/851515-senior-software-engineer-go-python/"
    assert vacancy.categories == frozenset({"Python"})
    assert vacancy.company == ""
    assert vacancy.is_remote is None
    assert vacancy.description.startswith("Our Client is a leading VC-backed defense")


def test_build_falls_back_to_requested_category(http_client: HttpClient) -> None:
    item = make_item(link="https://djinni.co/jobs/1-golang-engineer/")

    vacancy = DjinniCollector(http_client).build(item, "Golang")

    assert vacancy.categories == frozenset({"Golang"})
    assert vacancy.description == "Go and Kafka"


def test_build_rejects_unexpected_link(http_client: HttpClient) -> None:
    with pytest.raises(FeedFormatError, match="Unexpected Djinni job link"):
        DjinniCollector(http_client).build(make_item(link="https://djinni.co/jobs/"), "Python")
