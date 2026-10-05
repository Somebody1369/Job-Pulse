import pytest
from django.test import Client
from django.urls import reverse

from tests.utils import make_ingestor, make_vacancy_data
from vacancies.models import Source, Vacancy

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def vacancies() -> None:
    make_ingestor(Source.objects.get(code="dou")).ingest(
        [
            make_vacancy_data(
                external_id="1",
                title="Django Developer",
                company="Acme",
                description="Build REST APIs for payments.",
            ),
            make_vacancy_data(
                external_id="2",
                title="Backend Engineer",
                company="Globex",
                description="We use Django and Celery.",
            ),
            make_vacancy_data(
                external_id="3",
                title="Go Engineer",
                company="Initech",
                description="Kubernetes and Kafka.",
            ),
        ]
    )


def titles(text: str) -> list[str]:
    return [vacancy.title for vacancy in Vacancy.objects.search(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("django", ["Django Developer", "Backend Engineer"]),
        ("developers", ["Django Developer"]),
        ("django -celery", ["Django Developer"]),
        ('"rest apis"', ["Django Developer"]),
        ("kafka OR celery", ["Backend Engineer", "Go Engineer"]),
        ("rust", []),
    ],
)
def test_search_supports_stemming_and_operators(text: str, expected: list[str]) -> None:
    assert sorted(titles(text)) == sorted(expected)


def test_search_ranks_title_matches_higher() -> None:
    assert titles("django") == ["Django Developer", "Backend Engineer"]


@pytest.mark.parametrize(
    ("term", "expected"),
    [("kafka", 1), ("globex", 1), ("django", 2), ("   ", 3)],
)
def test_admin_search(admin_client: Client, term: str, expected: int) -> None:
    response = admin_client.get(reverse("admin:vacancies_vacancy_changelist"), {"q": term})

    assert response.status_code == 200
    assert response.context["cl"].result_count == expected
