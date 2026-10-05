from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
import responses
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from core.aggregates import Median, Percentile
from core.http import HttpClient
from market.models import SalaryResponse, SalarySurvey
from market.services import import_salary_survey
from market.surveys import (
    SURVEY_URL_TEMPLATE,
    SurveyFormatError,
    SurveyResponse,
    decode_survey,
    normalize_english,
    normalize_language,
    parse_experience,
    parse_salary,
    parse_survey,
    survey_period,
)

OLD_FORMAT = (
    "Timestamp,Ваша основна зайнятість,Зарплата / дохід в ІТ у $$$ за місяць,"
    "Оберіть вашу основну посаду,Ваш тайтл на цій посаді,Основна мова програмування,"
    "Загальний стаж роботи за нинішньою ІТ-спеціальністю,Знання англійської мови\n"
    "5/30/2024,Працюю,3000,Software Engineer,Middle,Python,5 років,Upper-Intermediate\n"
    "5/30/2024,Працюю,,QA Engineer,Junior,,1 рік,Intermediate\n"
    "5/30/2024,Працюю,250000,CEO,Head,,Понад 20 років,Advanced\n"
    "5/30/2024,Працюю,1200.5,Data Analyst,Junior,C#  NET,Півтора роки,4. Intermediate\n"
)
NEW_FORMAT = (
    "Submittedat,ЗАРПЛАТА СУМАРНИЙ ДОХІД в ІТ,Title_clean,Посади,Основна мова програмування,"
    "Загальний стаж роботи за нинішньою ІТ-спеціальністю,Знання англійської мови\n"
    "2026-06-08,4500,Senior,Software Engineer  Developer,Go,7,5. Upper-Intermediate\n"
    "2026-06-08,2000,Middle\n"
)


def test_survey_period() -> None:
    assert survey_period("2026_june") == date(2026, 6, 1)
    assert survey_period("2024_dec") == date(2024, 12, 1)


@pytest.mark.parametrize("name", ["2026_july", "june_2026", "latest"])
def test_survey_period_rejects_unknown_names(name: str) -> None:
    with pytest.raises(SurveyFormatError, match="survey name"):
        survey_period(name)


def test_decode_survey_supports_utf8_and_cp1251() -> None:
    assert decode_survey("﻿Зарплата".encode()) == "Зарплата"
    assert decode_survey("Зарплата".encode("cp1251")) == "Зарплата"


def test_decode_survey_rejects_unknown_encoding() -> None:
    with pytest.raises(SurveyFormatError, match="encoding"):
        decode_survey(b"\x98\x98")


def test_parse_survey_old_format() -> None:
    assert list(parse_survey(OLD_FORMAT)) == [
        SurveyResponse(
            salary_usd=3000,
            experience_years=Decimal(5),
            programming_language="Python",
            position="Software Engineer",
            seniority="Middle",
            english_level="Upper-Intermediate",
        ),
        SurveyResponse(
            salary_usd=1200,
            experience_years=Decimal("1.5"),
            programming_language="C# / .NET",
            position="Data Analyst",
            seniority="Junior",
            english_level="Intermediate",
        ),
    ]


def test_parse_survey_new_format_with_short_rows() -> None:
    senior, middle = parse_survey(NEW_FORMAT)

    assert senior.position == "Software Engineer Developer"
    assert (senior.seniority, senior.experience_years) == ("Senior", Decimal(7))
    assert middle == SurveyResponse(
        salary_usd=2000,
        experience_years=None,
        programming_language="",
        position="",
        seniority="Middle",
        english_level="",
    )


def test_parse_survey_without_optional_columns() -> None:
    text = "Зарплата,Основна мова програмування,Загальний стаж,Знання англійської\n1000,Go,2,B2\n"

    (response,) = parse_survey(text)

    assert (response.position, response.seniority) == ("", "")


@pytest.mark.parametrize(
    ("text", "message"),
    [("", "empty"), ("Зарплата,Основна мова програмування\n1000,Go\n", "загальний стаж")],
)
def test_parse_survey_rejects_unexpected_files(text: str, message: str) -> None:
    with pytest.raises(SurveyFormatError, match=message):
        list(parse_survey(text))


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3000", 3000), ("1 500,5", 1500), ("", None), ("0", None), ("100001", None), ("n/a", None)],
)
def test_parse_salary(value: str, expected: int | None) -> None:
    assert parse_salary(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Менше як 3 місяці", Decimal("0.1")),
        ("3 місяці", Decimal("0.25")),
        ("Пів року", Decimal("0.5")),
        ("Півтора роки", Decimal("1.5")),
        ("1 рік", Decimal(1)),
        ("15-20 років", Decimal(15)),
        ("Понад 20 років", Decimal(20)),
        ("0,25", Decimal("0.25")),
        ("-99", None),
        ("", None),
    ],
)
def test_parse_experience(value: str, expected: Decimal | None) -> None:
    assert parse_experience(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("C#  NET", "C# / .NET"),
        ("Bash  Shell", "Bash / Shell"),
        ("Не можу обрати одну основну мову", ""),
        ("  Python ", "Python"),
    ],
)
def test_normalize_language(value: str, expected: str) -> None:
    assert normalize_language(value) == expected


def test_normalize_english() -> None:
    assert normalize_english("6. Advanced") == "Advanced"
    assert normalize_english("Intermediate") == "Intermediate"


@pytest.mark.django_db
def test_import_salary_survey_replaces_previous_import(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    url = SURVEY_URL_TEMPLATE.format(name="2024_june")
    mocked_responses.get(url, body=OLD_FORMAT.encode("cp1251"))

    import_salary_survey(http_client, "2024_june")
    survey = import_salary_survey(http_client, "2024_june")

    assert survey.period == date(2024, 6, 1)
    assert survey.response_count == 2
    assert SalaryResponse.objects.count() == 2
    assert str(survey) == "DOU salary survey June 2024"
    assert (
        str(SalaryResponse.objects.get(salary_usd=3000)) == "$3000 in DOU salary survey June 2024"
    )


@pytest.mark.django_db
def test_median_and_percentiles(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(SURVEY_URL_TEMPLATE.format(name="2026_june"), body=NEW_FORMAT.encode())
    import_salary_survey(http_client, "2026_june")

    stats = SalaryResponse.objects.aggregate(
        median=Median("salary_usd"), p75=Percentile("salary_usd", 0.75)
    )

    assert stats == {"median": 3250.0, "p75": 3875.0}


def test_percentile_validates_fraction() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        Percentile("salary_usd", 1.5)


@pytest.mark.django_db
def test_import_salary_surveys_command(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(SURVEY_URL_TEMPLATE.format(name="2026_june"), body=NEW_FORMAT.encode())
    mocked_responses.get(SURVEY_URL_TEMPLATE.format(name="2025_dec"), status=404)
    output = StringIO()
    errors = StringIO()

    with pytest.raises(CommandError, match="Failed surveys: 2025_dec"):
        call_command(
            "import_salary_surveys",
            "-s",
            "2026_june",
            "-s",
            "2025_dec",
            stdout=output,
            stderr=errors,
        )

    assert "2026_june: 2 responses" in output.getvalue()
    assert "2025_dec: 404" in errors.getvalue()
    assert SalarySurvey.objects.get().name == "2026_june"


@pytest.mark.django_db
@pytest.mark.parametrize("model", ["salarysurvey", "salaryresponse"])
def test_survey_admin_renders(admin_client: Client, model: str) -> None:
    response = admin_client.get(reverse(f"admin:market_{model}_changelist"))

    assert response.status_code == 200
