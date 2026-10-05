from datetime import UTC, datetime
from io import StringIO

import pytest
import requests
import responses
from django.core.management import CommandError, call_command

from core.http import HttpClient
from market.services import UsdConverter
from tests.utils import (
    TEST_RATES,
    DenyList,
    StubCollector,
    make_ingestor,
    make_vacancy_data,
    read_fixture,
)
from vacancies.collectors.base import DetailsParseError, VacancyDetails
from vacancies.models import Company, ScrapeRun, Skill, Source, Vacancy
from vacancies.salary import SalaryRange
from vacancies.services import (
    CompanyResolver,
    IngestStats,
    VacancyEnricher,
    enrich_from_source,
    supports_details,
)
from vacancies.skills import SkillMatcher

pytestmark = pytest.mark.django_db

FETCHED_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
DJINNI_ROBOTS = "User-agent: *\nDisallow: /developers\n"


def job_url(external_id: str) -> str:
    return f"https://djinni.co/jobs/{external_id}-python-developer/"


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} error", response=response)


@pytest.fixture
def djinni() -> Source:
    return Source.objects.get(code="djinni")


def ingest_vacancies(source: Source, *external_ids: str) -> None:
    make_ingestor(source).ingest(
        [
            make_vacancy_data(
                external_id=external_id,
                url=job_url(external_id),
                company="",
                published_at=datetime(2026, 10, int(external_id), tzinfo=UTC),
            )
            for external_id in external_ids
        ]
    )


def test_enricher_applies_details_and_tracks_failures(djinni: Source) -> None:
    ingest_vacancies(djinni, "1", "2", "3", "4", "5")
    collector = StubCollector(
        {
            job_url("1"): VacancyDetails(
                company="Acme",
                company_website="https://acme.example",
                locations=("Київ",),
                is_remote=False,
                salary=SalaryRange(40000, 60000, "UAH"),
                experience_months=24,
                english_level="B2",
            ),
            job_url("2"): http_error(404),
            job_url("3"): http_error(500),
            job_url("4"): DetailsParseError("no structured data"),
        }
    )
    enricher = VacancyEnricher(
        collector,
        DenyList(job_url("5")),
        matcher=SkillMatcher.from_skills(Skill.objects.all()),
        converter=UsdConverter(TEST_RATES),
        fetched_at=FETCHED_AT,
    )

    stats = enricher.enrich(Vacancy.objects.order_by("external_id"))

    assert stats == IngestStats(fetched=5, created=0, updated=1, failed=4)
    enriched = Vacancy.objects.select_related("company").get(external_id="1")
    assert enriched.company is not None
    assert (enriched.company.name, enriched.company.website) == ("Acme", "https://acme.example")
    assert enriched.locations == ["Київ"]
    assert enriched.is_remote is False
    assert enriched.salary_text == "40000–60000 UAH"
    assert (enriched.salary_min_usd, enriched.salary_max_usd) == (1000, 1500)
    assert (enriched.experience_months, enriched.english_level) == (24, "B2")
    fetched = dict(Vacancy.objects.values_list("external_id", "details_fetched_at"))
    assert fetched == {
        "1": FETCHED_AT,
        "2": FETCHED_AT,
        "3": None,
        "4": None,
        "5": FETCHED_AT,
    }


def test_feed_updates_keep_enriched_details(djinni: Source) -> None:
    ingest_vacancies(djinni, "1")
    VacancyEnricher(
        StubCollector({job_url("1"): VacancyDetails(company="Acme", is_remote=True)}),
        DenyList(),
        matcher=SkillMatcher.from_skills(Skill.objects.all()),
        converter=UsdConverter(TEST_RATES),
        fetched_at=FETCHED_AT,
    ).enrich(Vacancy.objects.all())

    ingest_vacancies(djinni, "1")

    vacancy = Vacancy.objects.select_related("company").get()
    assert vacancy.company is not None
    assert vacancy.company.name == "Acme"
    assert vacancy.is_remote is True


def test_company_resolver_fills_missing_website_only() -> None:
    Company.objects.create(name="Acme", slug="acme")
    Company.objects.create(name="Globex", slug="globex", website="https://globex.example")
    resolver = CompanyResolver()

    acme = resolver.resolve("ACME", "https://acme.example")
    globex = resolver.resolve("Globex", "https://other.example")

    assert acme is not None
    assert globex is not None
    assert Company.objects.get(pk=acme.pk).website == "https://acme.example"
    assert Company.objects.get(pk=globex.pk).website == "https://globex.example"
    assert resolver.resolve("!!!") is None


def test_enrich_from_source_processes_latest_pending_vacancies(
    djinni: Source, http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    ingest_vacancies(djinni, "1", "2", "3")
    Vacancy.objects.filter(external_id="3").update(details_fetched_at=FETCHED_AT)
    mocked_responses.get("https://djinni.co/robots.txt", body=DJINNI_ROBOTS)
    mocked_responses.get(job_url("2"), body=read_fixture("djinni_job_remote.html"))

    run = enrich_from_source(djinni, http=http_client, limit=1)

    assert run.kind == ScrapeRun.Kind.DETAILS
    assert run.status == ScrapeRun.Status.SUCCEEDED
    assert (run.fetched_count, run.updated_count, run.failed_count) == (1, 1, 0)
    vacancy = Vacancy.objects.select_related("company").get(external_id="2")
    assert vacancy.company is not None
    assert vacancy.company.name == "Tailored Tech"
    assert Vacancy.objects.get(external_id="1").details_fetched_at is None


def test_enrich_from_source_rejects_sources_without_details(http_client: HttpClient) -> None:
    run = enrich_from_source(Source.objects.get(code="dou"), http=http_client, limit=10)

    assert run.status == ScrapeRun.Status.FAILED
    assert run.error.startswith("DetailsNotSupportedError")


def test_supports_details() -> None:
    unknown = Source(code="workua", name="Work.ua", homepage="https://www.work.ua/")

    assert supports_details(Source.objects.get(code="djinni"))
    assert not supports_details(Source.objects.get(code="dou"))
    assert not supports_details(unknown)


def test_enrich_command_uses_sources_with_details(
    djinni: Source, mocked_responses: responses.RequestsMock
) -> None:
    ingest_vacancies(djinni, "1")
    mocked_responses.get("https://djinni.co/robots.txt", body=DJINNI_ROBOTS)
    mocked_responses.get(job_url("1"), body=read_fixture("djinni_job_office.html"))
    output = StringIO()

    call_command("enrich_vacancies", "--limit", "5", stdout=output)

    assert "djinni: 1 vacancies, 0 new, 1 updated in" in output.getvalue()


def test_enrich_command_reports_failed_pages(
    djinni: Source, mocked_responses: responses.RequestsMock
) -> None:
    ingest_vacancies(djinni, "1")
    mocked_responses.get("https://djinni.co/robots.txt", body=DJINNI_ROBOTS)
    mocked_responses.get(job_url("1"), status=404)
    output = StringIO()

    call_command("enrich_vacancies", "--source", "djinni", stdout=output)

    assert "1 updated" not in output.getvalue()
    assert "0 updated, 1 failed" in output.getvalue()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (("--source", "dou"), "Not supported for: dou"),
        (("--limit", "0"), "must be a positive integer"),
    ],
)
def test_enrich_command_validates_arguments(arguments: tuple[str, ...], message: str) -> None:
    with pytest.raises(CommandError, match=message):
        call_command("enrich_vacancies", *arguments)


def test_enricher_rematches_skills_once_company_is_known(djinni: Source) -> None:
    make_ingestor(djinni).ingest(
        [
            make_vacancy_data(
                external_id="1",
                url=job_url("1"),
                company="",
                title="PR Manager",
                description="Ми — Spring Systems, продуктова компанія.",
            )
        ]
    )
    assert set(Vacancy.objects.get().skills.values_list("name", flat=True)) == {"Spring"}

    VacancyEnricher(
        StubCollector({job_url("1"): VacancyDetails(company="Spring Systems")}),
        DenyList(),
        matcher=SkillMatcher.from_skills(Skill.objects.all()),
        converter=UsdConverter(TEST_RATES),
        fetched_at=FETCHED_AT,
    ).enrich(Vacancy.objects.all())

    assert not Vacancy.objects.get().skills.exists()
