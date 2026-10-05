from datetime import UTC, datetime, timedelta

import pytest
import responses
from responses import matchers

from core.http import HttpClient
from tests.utils import DOU_FEED_URL, make_vacancy_data, read_fixture
from vacancies.models import Company, ScrapeRun, Skill, Source, Vacancy
from vacancies.services import (
    IngestStats,
    VacancyIngestor,
    collect_from_source,
    merge_duplicates,
)
from vacancies.skills import SkillMatcher

FIRST_SEEN = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
LAST_SEEN = FIRST_SEEN + timedelta(hours=1)


class FailingMatcher(SkillMatcher):
    def match(self, text: str) -> set[int]:
        if "Broken" in text:
            raise RuntimeError("matcher failure")
        return set()


@pytest.fixture
def dou() -> Source:
    return Source.objects.get(code="dou")


@pytest.fixture
def matcher() -> SkillMatcher:
    return SkillMatcher.from_skills(Skill.objects.all())


def skill_names(vacancy: Vacancy) -> set[str]:
    return set(vacancy.skills.values_list("name", flat=True))


def test_merge_duplicates_unites_categories_and_keeps_latest_data() -> None:
    merged = merge_duplicates(
        [
            make_vacancy_data(title="Old title", categories=frozenset({"Python"})),
            make_vacancy_data(external_id="2"),
            make_vacancy_data(title="New title", categories=frozenset({"Django"})),
        ]
    )

    assert list(merged) == ["1", "2"]
    assert merged["1"].title == "New title"
    assert merged["1"].categories == frozenset({"Python", "Django"})


@pytest.mark.django_db
def test_ingest_creates_vacancies_with_companies_and_skills(
    dou: Source, matcher: SkillMatcher
) -> None:
    ingestor = VacancyIngestor(dou, matcher=matcher, seen_at=FIRST_SEEN)

    stats = ingestor.ingest(
        [
            make_vacancy_data(external_id="1", company="Acme Corp"),
            make_vacancy_data(
                external_id="2",
                company="ACME corp",
                title="Golang Engineer",
                description="Kubernetes and Kafka.",
            ),
            make_vacancy_data(external_id="3", company=""),
        ]
    )

    assert stats == IngestStats(fetched=3, created=3, updated=0)
    assert Company.objects.count() == 1
    first, second, third = Vacancy.objects.order_by("external_id")
    assert first.company == second.company
    assert third.company is None
    assert skill_names(first) == {"Python", "Django", "PostgreSQL"}
    assert skill_names(second) == {"Go", "Kubernetes", "Kafka"}
    assert first.first_seen_at == first.last_seen_at == FIRST_SEEN


@pytest.mark.django_db
def test_ingest_updates_existing_vacancy(dou: Source, matcher: SkillMatcher) -> None:
    VacancyIngestor(dou, matcher=matcher, seen_at=FIRST_SEEN).ingest([make_vacancy_data()])

    stats = VacancyIngestor(dou, matcher=matcher, seen_at=LAST_SEEN).ingest(
        [
            make_vacancy_data(
                title="Senior Python Developer",
                categories=frozenset({"Django"}),
                description="FastAPI only.",
            )
        ]
    )

    assert stats == IngestStats(fetched=1, created=0, updated=1)
    vacancy = Vacancy.objects.get()
    assert vacancy.title == "Senior Python Developer"
    assert vacancy.categories == ["Django", "Python"]
    assert skill_names(vacancy) == {"Python", "FastAPI"}
    assert vacancy.first_seen_at == FIRST_SEEN
    assert vacancy.last_seen_at == LAST_SEEN


@pytest.mark.django_db
def test_ingest_keeps_same_external_id_from_different_sources_apart(
    dou: Source, matcher: SkillMatcher
) -> None:
    djinni = Source.objects.get(code="djinni")

    VacancyIngestor(dou, matcher=matcher, seen_at=FIRST_SEEN).ingest([make_vacancy_data()])
    VacancyIngestor(djinni, matcher=matcher, seen_at=FIRST_SEEN).ingest([make_vacancy_data()])

    assert Vacancy.objects.count() == 2


@pytest.mark.django_db
def test_ingest_is_atomic(dou: Source) -> None:
    ingestor = VacancyIngestor(dou, matcher=FailingMatcher({}), seen_at=FIRST_SEEN)

    with pytest.raises(RuntimeError, match="matcher failure"):
        ingestor.ingest([make_vacancy_data(), make_vacancy_data(external_id="2", title="Broken")])

    assert not Vacancy.objects.exists()
    assert not Company.objects.exists()


@pytest.mark.django_db
def test_collect_from_source_records_successful_run(
    dou: Source, http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        DOU_FEED_URL,
        body=read_fixture("dou_python.xml"),
        match=[matchers.query_param_matcher({"category": "Python"})],
    )

    run = collect_from_source(dou, ["Python"], http=http_client)

    assert run.status == ScrapeRun.Status.SUCCEEDED
    assert (run.fetched_count, run.created_count, run.updated_count) == (5, 5, 0)
    assert run.categories == ["Python"]
    assert run.finished_at is not None
    vacancy = Vacancy.objects.select_related("company").get(external_id="339058")
    assert vacancy.salary_text == "$1200–2800"
    assert vacancy.is_remote is False
    assert vacancy.company is not None
    assert vacancy.company.name == "429 окрема бригада безпілотних систем «АХІЛЛЕС»"


@pytest.mark.django_db
def test_collect_from_source_records_http_failure(
    dou: Source, http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(DOU_FEED_URL, status=503)

    run = collect_from_source(dou, ["Python"], http=http_client)

    assert run.status == ScrapeRun.Status.FAILED
    assert run.error.startswith("HTTPError: 503")
    assert not Vacancy.objects.exists()


@pytest.mark.django_db
def test_collect_from_source_records_unknown_collector(http_client: HttpClient) -> None:
    source = Source.objects.create(
        code="workua", name="Work.ua", homepage="https://www.work.ua/", kind=Source.Kind.HTML
    )

    run = collect_from_source(source, ["Python"], http=http_client)

    assert run.status == ScrapeRun.Status.FAILED
    assert run.error.startswith("UnknownSourceError")
