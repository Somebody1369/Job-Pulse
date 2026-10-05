from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
import responses
from pytest_django.fixtures import Settings
from responses import matchers

from core.http import HttpClient
from tests.utils import make_ingestor, make_vacancy_data
from vacancies.collectors.ats import Board, mentions_location, parse_boards
from vacancies.collectors.greenhouse import GREENHOUSE_JOBS_URL, GreenhouseCollector
from vacancies.collectors.lever import LEVER_POSTINGS_URL, LeverCollector
from vacancies.collectors.registry import COLLECTORS
from vacancies.models import ScrapeRun, Source, Vacancy
from vacancies.salary import SalaryRange
from vacancies.services import collect_from_source

KEYWORDS = ("ukraine", "kyiv", "europe")


def greenhouse_job(job_id: int, location: str, *, offices: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": " Senior Python Engineer ",
        "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{job_id}",
        "company_name": "Acme Inc.",
        "location": {"name": location},
        "offices": [{"name": name} for name in offices],
        "departments": [{"name": "Engineering"}, {"name": ""}],
        "content": "&lt;p&gt;Python, Django &amp;amp; PostgreSQL&lt;/p&gt;",
        "first_published": None,
        "updated_at": "2026-10-01T10:00:00-04:00",
    }


def lever_posting(posting_id: str, **overrides: Any) -> dict[str, Any]:
    posting: dict[str, Any] = {
        "id": posting_id,
        "text": "Backend Developer",
        "hostedUrl": f"https://jobs.lever.co/acme/{posting_id}",
        "createdAt": 1791100000000,
        "workplaceType": "onsite",
        "country": "UA",
        "categories": {
            "location": "Kyiv",
            "allLocations": ["Kyiv", "Lviv"],
            "department": "R&D",
            "team": "Core",
        },
        "description": "<p>Go and Kafka.</p>",
        "lists": [{"text": "Requirements", "content": "<li>Kubernetes</li>"}],
        "additional": "<p>Remote friendly.</p>",
    }
    return posting | overrides


def test_parse_boards_and_locations() -> None:
    assert parse_boards(["ajax=Ajax Systems", " eleks ", "", "=Nameless"]) == [
        Board("ajax", "Ajax Systems"),
        Board("eleks"),
    ]
    assert mentions_location(["Remote (Ukraine)"], KEYWORDS)
    assert not mentions_location(["New York"], KEYWORDS)


def test_greenhouse_collects_relevant_jobs(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        GREENHOUSE_JOBS_URL.format(token="acme"),
        json={
            "jobs": [
                greenhouse_job(
                    1, "Remote (Europe)", offices=("Remote (Europe)", "Remote (Ukraine)")
                ),
                greenhouse_job(2, "San Francisco"),
            ]
        },
        match=[matchers.query_param_matcher({"content": "true"})],
    )
    collector = GreenhouseCollector(http_client, boards=[Board("acme")], keywords=KEYWORDS)

    (vacancy,) = collector.collect(["Python"])

    assert vacancy.external_id == "1"
    assert vacancy.title == "Senior Python Engineer"
    assert vacancy.company == "Acme Inc."
    assert vacancy.locations == ("Remote (Europe)", "Remote (Ukraine)")
    assert vacancy.is_remote is True
    assert vacancy.categories == frozenset({"Engineering"})
    assert vacancy.description == "Python, Django & PostgreSQL"
    assert vacancy.published_at == datetime(2026, 10, 1, 10, tzinfo=timezone(timedelta(hours=-4)))


def test_greenhouse_board_company_overrides_api_name(http_client: HttpClient) -> None:
    job = greenhouse_job(3, "Kyiv") | {"first_published": "2026-09-01T09:00:00+00:00"}

    vacancy = GreenhouseCollector(http_client, boards=[], keywords=KEYWORDS).build(
        job, Board("acme", "Acme")
    )

    assert vacancy.company == "Acme"
    assert vacancy.is_remote is False
    assert vacancy.published_at == datetime(2026, 9, 1, 9, tzinfo=UTC)


def test_lever_collects_ukrainian_and_remote_postings(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        LEVER_POSTINGS_URL.format(token="acme"),
        json=[
            lever_posting("ua"),
            lever_posting("remote", country="PL", workplaceType="remote"),
            lever_posting(
                "europe",
                country="DE",
                categories={"location": "Berlin, Europe"},
            ),
            lever_posting("paris", country="FR", categories={"location": "Paris"}),
        ],
        match=[matchers.query_param_matcher({"mode": "json"})],
    )
    collector = LeverCollector(http_client, boards=[Board("acme", "Acme")], keywords=KEYWORDS)

    vacancies = collector.collect([])

    assert [vacancy.external_id for vacancy in vacancies] == ["ua", "remote", "europe"]
    first = vacancies[0]
    assert first.company == "Acme"
    assert first.locations == ("Kyiv", "Lviv")
    assert first.categories == frozenset({"R&D", "Core"})
    assert first.is_remote is False
    assert first.description.splitlines() == [
        "Go and Kafka.",
        "Requirements",
        "• Kubernetes",
        "Remote friendly.",
    ]
    assert first.published_at == datetime.fromtimestamp(1791100000, tz=UTC)
    assert vacancies[1].is_remote is True
    assert vacancies[2].locations == ("Berlin, Europe",)


@pytest.mark.parametrize(
    ("salary_range", "expected"),
    [
        (
            {"currency": "usd", "interval": "per-year-salary", "min": 60000, "max": 72000},
            SalaryRange(5000, 6000, "USD"),
        ),
        (
            {"currency": "UAH", "interval": "per-month-salary", "min": 80000, "max": None},
            SalaryRange(80000, None, "UAH"),
        ),
        ({"currency": "USD", "interval": "per-hour-wage", "min": 40, "max": 60}, None),
        ({"interval": "per-month-salary", "min": 1000}, None),
        (None, None),
    ],
)
def test_lever_salary(
    http_client: HttpClient, salary_range: dict[str, Any] | None, expected: SalaryRange | None
) -> None:
    posting = lever_posting("salary", salaryRange=salary_range, categories={})

    vacancy = LeverCollector(http_client, boards=[], keywords=KEYWORDS).build(
        posting, Board("acme")
    )

    assert vacancy.salary == expected
    assert vacancy.company == "acme"
    assert vacancy.locations == ()


def test_collectors_use_boards_from_settings(
    settings: Settings, http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    settings.GREENHOUSE_BOARDS = ["acme"]
    settings.LEVER_BOARDS = ["globex=Globex"]
    mocked_responses.get(
        GREENHOUSE_JOBS_URL.format(token="acme"), json={"jobs": [greenhouse_job(1, "Kyiv")]}
    )
    mocked_responses.get(LEVER_POSTINGS_URL.format(token="globex"), json=[lever_posting("ua")])

    assert set(COLLECTORS) >= {"greenhouse", "lever"}
    assert [vacancy.company for vacancy in GreenhouseCollector(http_client).collect([])] == [
        "Acme Inc."
    ]
    assert [vacancy.company for vacancy in LeverCollector(http_client).collect([])] == ["Globex"]


@pytest.mark.django_db
def test_ats_vacancies_are_matched_with_job_board_postings(
    settings: Settings, http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    settings.LEVER_BOARDS = ["ajax=Ajax Systems"]
    make_ingestor(Source.objects.get(code="dou")).ingest(
        [make_vacancy_data(external_id="1", title="Backend Developer", company="Ajax Systems")]
    )
    mocked_responses.get(LEVER_POSTINGS_URL.format(token="ajax"), json=[lever_posting("ua")])
    lever = Source.objects.get(code="lever")

    run = collect_from_source(lever, ["Python"], http=http_client)

    assert run.status == ScrapeRun.Status.SUCCEEDED
    assert run.fetched_count == 1
    assert Vacancy.objects.distinct_postings().count() == 1
