from datetime import UTC, datetime

import pytest
import responses
from responses import matchers

from core.http import HttpClient
from tests.utils import DOU_FEED_URL, read_fixture
from vacancies.collectors.dou import DouCollector, DouTitle, parse_title
from vacancies.collectors.rss import FeedFormatError, FeedItem


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Python developer with AI (AWS) в IT SmartFlex, віддалено",
            DouTitle(
                position="Python developer with AI (AWS)", company="IT SmartFlex", is_remote=True
            ),
        ),
        (
            "Python Software Engineer в PlantIn, Київ, віддалено",
            DouTitle(
                position="Python Software Engineer",
                company="PlantIn",
                locations=("Київ",),
                is_remote=True,
            ),
        ),
        (
            "Python Software Engineer в Inoxoft, $2800–3500, за кордоном, віддалено",
            DouTitle(
                position="Python Software Engineer",
                company="Inoxoft",
                locations=("за кордоном",),
                salary_text="$2800–3500",
                is_remote=True,
            ),
        ),
        (
            'Розробник ПЗ в 411 Окрема Бригада БПС "Яструби", $700–1100, Запоріжжя',
            DouTitle(
                position="Розробник ПЗ",
                company='411 Окрема Бригада БПС "Яструби"',
                locations=("Запоріжжя",),
                salary_text="$700–1100",
            ),
        ),
        (
            "QA Engineer в Acme, від 40 000 грн, Київ",
            DouTitle(
                position="QA Engineer",
                company="Acme",
                locations=("Київ",),
                salary_text="від 40 000 грн",
            ),
        ),
        (
            "Python розробник в команду AI в Acme, Львів",
            DouTitle(
                position="Python розробник в команду AI", company="Acme", locations=("Львів",)
            ),
        ),
        ("Python Developer", DouTitle(position="Python Developer")),
    ],
)
def test_parse_title(raw: str, expected: DouTitle) -> None:
    assert parse_title(raw) == expected


def test_collect_builds_vacancies_from_feed(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        DOU_FEED_URL,
        body=read_fixture("dou_python.xml"),
        match=[matchers.query_param_matcher({"category": "Python"})],
    )

    vacancies = DouCollector(http_client).collect("Python")

    assert [vacancy.external_id for vacancy in vacancies] == [
        "357643",
        "375469",
        "339058",
        "362687",
        "375411",
    ]
    vacancy = vacancies[3]
    assert vacancy.url == "https://jobs.dou.ua/companies/agileengine/vacancies/362687/"
    assert vacancy.title == "Application Security Engineer ID71662"
    assert vacancy.company == "AgileEngine"
    assert vacancy.locations == ("Львів", "Краків (Польща)")
    assert vacancy.is_remote is True
    assert vacancy.categories == frozenset({"Python"})
    assert vacancy.description.startswith("Hi there! AgileEngine")
    assert "Відгукнутись" not in vacancy.description
    assert "#reply-btn-id" in vacancy.description_html


def test_build_rejects_unexpected_link(http_client: HttpClient) -> None:
    item = FeedItem(
        title="Python Developer в Acme",
        link="https://jobs.dou.ua/companies/acme/",
        description_html="",
        published_at=datetime(2026, 10, 1, tzinfo=UTC),
        categories=(),
    )

    with pytest.raises(FeedFormatError, match="Unexpected DOU vacancy link"):
        DouCollector(http_client).build(item, "Python")
