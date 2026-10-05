import json
from typing import Any

import pytest
from bs4 import BeautifulSoup

from vacancies.collectors.jsonld import details_from_job_posting, find_job_posting
from vacancies.salary import NO_SALARY, SalaryRange


def page(*payloads: str) -> BeautifulSoup:
    scripts = "".join(
        f'<script type="application/ld+json">{payload}</script>' for payload in payloads
    )
    return BeautifulSoup(f"<html><head>{scripts}</head></html>", "lxml")


def test_find_job_posting_skips_invalid_and_unrelated_blocks() -> None:
    soup = page(
        "{not json",
        json.dumps({"@type": "Organization", "name": "Acme"}),
        json.dumps({"@graph": [{"@type": "WebPage"}, {"@type": "JobPosting", "title": "Dev"}]}),
    )

    assert find_job_posting(soup) == {"@type": "JobPosting", "title": "Dev"}


def test_find_job_posting_supports_top_level_lists() -> None:
    soup = page(json.dumps([{"@type": "BreadcrumbList"}, {"@type": "JobPosting", "title": "QA"}]))

    assert find_job_posting(soup) == {"@type": "JobPosting", "title": "QA"}


def test_find_job_posting_returns_none_without_posting() -> None:
    assert find_job_posting(page(json.dumps({"@type": "WebSite"}))) is None


def test_details_from_full_job_posting() -> None:
    details = details_from_job_posting(
        {
            "hiringOrganization": {"name": " Acme ", "sameAs": "https://acme.example"},
            "jobLocation": [
                {"address": {"addressLocality": ["Київ", "Львів"], "addressCountry": "Україна"}},
                {"address": {"addressLocality": "Київ"}},
                {"address": {"addressCountry": "Польща"}},
            ],
            "jobLocationType": "TELECOMMUTE",
            "baseSalary": {
                "currency": "usd",
                "value": {"minValue": 3000, "maxValue": 4500.0, "unitText": "MONTH"},
            },
            "experienceRequirements": {"monthsOfExperience": 36.0},
        }
    )

    assert details.company == "Acme"
    assert details.company_website == "https://acme.example"
    assert details.locations == ("Київ", "Львів", "Польща")
    assert details.is_remote is True
    assert details.salary == SalaryRange(3000, 4500, "USD")
    assert details.experience_months == 36


@pytest.mark.parametrize(
    ("base_salary", "expected"),
    [
        ({"currency": "EUR", "value": {"value": 5000}}, SalaryRange(5000, 5000, "EUR")),
        ({"currency": "USD", "value": 2500}, SalaryRange(2500, 2500, "USD")),
        ({"currency": "USD", "value": {"minValue": 30, "unitText": "HOUR"}}, NO_SALARY),
        ({"value": {"minValue": 3000}}, NO_SALARY),
        ({"currency": "USD", "value": {"minValue": True}}, NO_SALARY),
        ("3000 USD", NO_SALARY),
    ],
)
def test_details_salary_variants(base_salary: Any, expected: SalaryRange) -> None:
    assert details_from_job_posting({"baseSalary": base_salary}).salary == expected


def test_details_from_minimal_job_posting() -> None:
    details = details_from_job_posting({"title": "Developer"})

    assert details.company == ""
    assert details.locations == ()
    assert details.is_remote is False
    assert details.salary == NO_SALARY
    assert details.experience_months is None
