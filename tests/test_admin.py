import pytest
from django.test import Client
from django.urls import reverse

from tests.utils import make_vacancy_data
from vacancies.models import ScrapeRun, Skill, Source, Vacancy
from vacancies.services import IngestStats, VacancyIngestor
from vacancies.skills import SkillMatcher

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def vacancy() -> Vacancy:
    source = Source.objects.get(code="dou")
    run = ScrapeRun.objects.create(source=source, categories=["Python"])
    VacancyIngestor(
        source, matcher=SkillMatcher.from_skills(Skill.objects.all()), seen_at=run.started_at
    ).ingest([make_vacancy_data()])
    run.mark_succeeded(IngestStats(fetched=1, created=1, updated=0))
    return Vacancy.objects.get()


@pytest.mark.parametrize("model", ["source", "company", "skill", "vacancy", "scraperun"])
def test_changelist_renders(admin_client: Client, model: str) -> None:
    response = admin_client.get(reverse(f"admin:vacancies_{model}_changelist"))

    assert response.status_code == 200


def test_vacancy_change_page_links_to_original(admin_client: Client, vacancy: Vacancy) -> None:
    response = admin_client.get(reverse("admin:vacancies_vacancy_change", args=[vacancy.pk]))

    assert response.status_code == 200
    assert 'href="https://example.com/jobs/1/"' in response.content.decode()


def test_scrape_runs_are_read_only(admin_client: Client) -> None:
    run = ScrapeRun.objects.get()

    assert admin_client.get(reverse("admin:vacancies_scraperun_add")).status_code == 403
    response = admin_client.post(
        reverse("admin:vacancies_scraperun_change", args=[run.pk]), {"status": "failed"}
    )
    assert response.status_code == 403


def test_root_redirects_to_admin(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == reverse("admin:index")
