from datetime import UTC, datetime

import pytest

from market.services import UsdConverter
from tests.utils import TEST_RATES, DenyList, StubCollector, make_ingestor, make_vacancy_data
from vacancies.collectors.base import VacancyDetails
from vacancies.dedup import company_key, title_key, vacancy_fingerprint
from vacancies.models import Skill, Source, Vacancy
from vacancies.services import VacancyEnricher
from vacancies.skills import SkillMatcher


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("PlantIn (Genesis)", "plantin"),
        ("Digis (a Fiverr company)", "digis"),
        ("Precoro Inc.", "precoro"),
        ("SoftServe, LLC", "softserve"),
        ("ТОВ «Львівські технології»", "львівські-технології"),
        ("Ltd", "ltd"),
        ("N-iX", "n-ix"),
    ],
)
def test_company_key(name: str, expected: str) -> None:
    assert company_key(name) == expected


def test_title_key_ignores_case_and_punctuation() -> None:
    assert title_key("Middle  Python-Developer (ML)!") == "middle python developer ml"


def test_vacancy_fingerprint() -> None:
    first = vacancy_fingerprint(company="acme", title="Python Developer", fallback="1:1")
    second = vacancy_fingerprint(company="acme", title="python developer.", fallback="2:7")

    assert first == second
    assert len(first) == 40
    assert (
        vacancy_fingerprint(company="acme", title="Senior Python Developer", fallback="") != first
    )
    assert vacancy_fingerprint(company="", title="Python Developer", fallback="2:7") == "2:7"


@pytest.mark.django_db
def test_same_posting_on_different_sources_shares_fingerprint() -> None:
    dou = Source.objects.get(code="dou")
    djinni = Source.objects.get(code="djinni")
    make_ingestor(dou).ingest(
        [
            make_vacancy_data(external_id="1", company="Acme", title="Python Developer"),
            make_vacancy_data(external_id="2", company="Acme", title="Senior Python Developer"),
        ]
    )
    make_ingestor(djinni).ingest(
        [
            make_vacancy_data(
                external_id="9",
                url="https://djinni.co/jobs/9-python-developer/",
                company="",
                title="Python developer",
                published_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
        ]
    )
    djinni_vacancy = Vacancy.objects.get(source=djinni)
    assert djinni_vacancy.fingerprint == f"{djinni.pk}:9"
    assert Vacancy.objects.distinct_postings().count() == 3

    VacancyEnricher(
        StubCollector(
            {"https://djinni.co/jobs/9-python-developer/": VacancyDetails(company="Acme Ltd")}
        ),
        DenyList(),
        matcher=SkillMatcher.from_skills(Skill.objects.all()),
        converter=UsdConverter(TEST_RATES),
        fetched_at=datetime(2026, 10, 5, tzinfo=UTC),
    ).enrich(Vacancy.objects.filter(source=djinni).select_related("company"))

    djinni_vacancy.refresh_from_db()
    assert djinni_vacancy.fingerprint == Vacancy.objects.get(external_id="1").fingerprint
    postings = Vacancy.objects.distinct_postings()
    assert postings.count() == 2
    assert {posting.title for posting in postings} == {
        "Senior Python Developer",
        "Python developer",
    }
