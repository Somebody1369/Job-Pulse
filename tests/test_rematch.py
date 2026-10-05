from io import StringIO

import pytest
from django.core.management import call_command

from tests.utils import make_ingestor, make_vacancy_data
from vacancies.models import Skill, Source, Vacancy
from vacancies.services import rematch_skills

pytestmark = pytest.mark.django_db


def skill_names(external_id: str) -> set[str]:
    return set(Vacancy.objects.get(external_id=external_id).skills.values_list("name", flat=True))


@pytest.fixture(autouse=True)
def vacancies() -> None:
    make_ingestor(Source.objects.get(code="dou")).ingest(
        [
            make_vacancy_data(external_id="1", description="Django and PostgreSQL."),
            make_vacancy_data(
                external_id="2", title="Data Engineer", description="dbt and Airflow."
            ),
        ]
    )


def test_rematch_skills_applies_dictionary_changes() -> None:
    Skill.objects.create(name="dbt", slug="dbt")
    Skill.objects.filter(name="PostgreSQL").update(stop_phrases=["PostgreSQL"])

    assert rematch_skills() == 4

    assert skill_names("1") == {"Python", "Django"}
    assert skill_names("2") == {"dbt", "Apache Airflow"}


def test_rematch_skills_command() -> None:
    output = StringIO()

    call_command("rematch_skills", stdout=output)

    assert "Linked 4 vacancy skills" in output.getvalue()
