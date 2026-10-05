from datetime import UTC, datetime

import pytest
import responses
from responses import matchers

from core.http import HttpClient
from tests.utils import DJINNI_FEED_URL, read_fixture
from vacancies.collectors.base import DetailsParseError
from vacancies.collectors.djinni import DjinniCollector, parse_job_page
from vacancies.collectors.rss import FeedFormatError, FeedItem
from vacancies.salary import NO_SALARY, SalaryRange

JOB_URL = "https://djinni.co/jobs/851100-python-developer/"


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

    vacancies = DjinniCollector(http_client).collect(["Python"])

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


def test_parse_job_page_with_published_salary() -> None:
    details = parse_job_page(read_fixture("djinni_job_remote.html"))

    assert details.company == "Tailored Tech"
    assert details.company_website == "https://tailored-tech.org"
    assert details.is_remote is True
    assert details.locations == ()
    assert details.salary == SalaryRange(1500, 2500, "USD")
    assert details.experience_months == 36
    assert details.english_level == "B2"


def test_parse_job_page_for_office_vacancy_without_salary() -> None:
    details = parse_job_page(read_fixture("djinni_job_office.html"))

    assert details.company == "Precoro"
    assert details.is_remote is False
    assert details.locations == ("Київ",)
    assert details.salary == NO_SALARY
    assert details.english_level == ""


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (b'<span class="detail-rows__value">B2', b'<span class="other">B2'),
        (b"B2 \xe2\x80\x93", b"Fluent \xe2\x80\x93"),
    ],
)
def test_parse_job_page_ignores_unrecognized_language_rows(
    original: bytes, replacement: bytes
) -> None:
    markup = read_fixture("djinni_job_remote.html").replace(original, replacement)

    assert parse_job_page(markup).english_level == ""


def test_parse_job_page_without_structured_data() -> None:
    with pytest.raises(DetailsParseError, match="JobPosting"):
        parse_job_page("<html><body>Vacancy closed</body></html>")


def test_fetch_details_downloads_job_page(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(JOB_URL, body=read_fixture("djinni_job_office.html"))

    assert DjinniCollector(http_client).fetch_details(JOB_URL).company == "Precoro"
