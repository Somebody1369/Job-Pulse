from datetime import timedelta

import pytest

from tests.utils import make_vacancy_data
from vacancies.models import ScrapeRun, Skill, Source
from vacancies.services import IngestStats, VacancyIngestor
from vacancies.skills import SkillMatcher

pytestmark = pytest.mark.django_db


@pytest.fixture
def run() -> ScrapeRun:
    return ScrapeRun.objects.create(source=Source.objects.get(code="dou"), categories=["Python"])


def test_running_scrape_run_has_no_duration(run: ScrapeRun) -> None:
    assert run.status == ScrapeRun.Status.RUNNING
    assert run.duration is None


def test_mark_succeeded_stores_stats(run: ScrapeRun) -> None:
    run.mark_succeeded(IngestStats(fetched=10, created=4, updated=6))

    run.refresh_from_db()
    assert run.status == ScrapeRun.Status.SUCCEEDED
    assert (run.fetched_count, run.created_count, run.updated_count) == (10, 4, 6)
    assert run.duration is not None
    assert run.duration >= timedelta(0)


def test_mark_failed_stores_error(run: ScrapeRun) -> None:
    run.mark_failed(RuntimeError("feed is down"))

    run.refresh_from_db()
    assert run.status == ScrapeRun.Status.FAILED
    assert run.error == "RuntimeError: feed is down"
    assert run.finished_at is not None


def test_string_representations(run: ScrapeRun) -> None:
    source = run.source
    VacancyIngestor(source, matcher=SkillMatcher.from_skills([]), seen_at=run.started_at).ingest(
        [make_vacancy_data()]
    )
    vacancy = source.vacancies.select_related("company").get()

    assert str(source) == "DOU"
    assert str(vacancy) == "Python Developer"
    assert str(vacancy.company) == "Acme"
    assert str(Skill.objects.get(name="C#")) == "C#"
    assert str(run).startswith("DOU at ")
    assert Skill.objects.get(name="Go").variants == ["Go", "Golang", "golang"]
