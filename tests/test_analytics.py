from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from analytics import queries
from analytics.dashboard import Dashboard, Filters
from analytics.forms import FilterForm
from market.models import MarketSnapshot, SalaryResponse, SalarySurvey
from tests.utils import make_ingestor, make_vacancy_data
from vacancies.models import Source

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
TODAY = NOW.date()


def snapshot(category: str, label: str, day: date, **fields: Any) -> MarketSnapshot:
    values: dict[str, Any] = {
        "active_candidates": 1000,
        "expected_min": 1500,
        "expected_max": 3500,
        "offers_per_candidate": Decimal("0.4"),
        "vacancies_online": 100,
        "vacancies_change": -5,
        "offered_min": 2000,
        "offered_max": 4000,
        "applications_per_vacancy": Decimal("50.5"),
    }
    return MarketSnapshot.objects.create(
        category=category, category_label=label, calculated_on=day, **(values | fields)
    )


def responses(survey: SalarySurvey, count: int, *, start: int, **fields: Any) -> None:
    values = {"programming_language": "Python", "seniority": "Middle", "experience_years": 4}
    SalaryResponse.objects.bulk_create(
        SalaryResponse(survey=survey, salary_usd=start + index * 100, **(values | fields))
        for index in range(count)
    )


@pytest.fixture
def market() -> None:
    snapshot("", "All categories", TODAY - timedelta(days=1), active_candidates=40000)
    snapshot("python", "Python", TODAY - timedelta(days=2), active_candidates=1500)
    snapshot("python", "Python", TODAY - timedelta(days=1), active_candidates=1700)
    snapshot("golang", "Golang", TODAY - timedelta(days=1), active_candidates=300)
    snapshot("ios", "iOS", TODAY - timedelta(days=1), vacancies_online=0)
    snapshot("python", "Python", TODAY - timedelta(days=120), active_candidates=900)


@pytest.fixture
def survey() -> SalarySurvey:
    previous = SalarySurvey.objects.create(
        name="2025_dec", period=date(2025, 12, 1), source_url="https://example.com/2025_dec.csv"
    )
    latest = SalarySurvey.objects.create(
        name="2026_june", period=date(2026, 6, 1), source_url="https://example.com/2026_june.csv"
    )
    responses(previous, 21, start=1000)
    responses(latest, 21, start=500, seniority="Junior", experience_years=Decimal("0.5"))
    responses(latest, 21, start=2000, seniority="Middle", experience_years=4)
    responses(latest, 21, start=4000, seniority="Senior", experience_years=12)
    responses(latest, 25, start=1000, seniority="Немає тайтлу", experience_years=None)
    responses(latest, 5, start=9000, seniority="Head", experience_years=20)
    responses(latest, 21, start=1500, programming_language="Go", seniority="Middle")
    return latest


@pytest.fixture
def vacancies() -> None:
    dou = Source.objects.get(code="dou")
    djinni = Source.objects.get(code="djinni")
    make_ingestor(dou).ingest(
        [
            make_vacancy_data(external_id="1", published_at=NOW - timedelta(days=1)),
            make_vacancy_data(
                external_id="2",
                title="Go Engineer",
                description="Kafka",
                published_at=NOW - timedelta(days=10),
            ),
            make_vacancy_data(
                external_id="3", title="Old Python job", published_at=NOW - timedelta(days=40)
            ),
        ]
    )
    make_ingestor(djinni).ingest(
        [make_vacancy_data(external_id="9", published_at=NOW - timedelta(days=2))]
    )


@pytest.mark.usefixtures("market")
def test_market_overview_uses_latest_snapshot_per_category() -> None:
    rows = queries.market_overview()

    assert [row.label for row in rows] == ["All categories", "Python", "Golang", "iOS"]
    assert rows[1].candidates == 1700
    assert rows[1].candidates_per_vacancy == 17.0
    assert rows[3].candidates_per_vacancy is None


@pytest.mark.usefixtures("market")
def test_market_trend_and_categories() -> None:
    trend = queries.market_trend("python", days=90, today=TODAY)

    assert [(point.day, point.candidates) for point in trend] == [
        (TODAY - timedelta(days=2), 1500),
        (TODAY - timedelta(days=1), 1700),
    ]
    assert queries.market_categories() == [
        ("", "All categories"),
        ("golang", "Golang"),
        ("ios", "iOS"),
        ("python", "Python"),
    ]


@pytest.mark.usefixtures("vacancies")
def test_skill_demand_counts_distinct_postings_per_period() -> None:
    rows = {row.skill: row for row in queries.skill_demand(now=NOW, days=7, limit=10)}

    assert (rows["Python"].current, rows["Python"].previous, rows["Python"].change) == (1, 0, 1)
    assert (rows["Kafka"].current, rows["Kafka"].previous) == (0, 1)
    assert "Old Python job" not in rows


def test_salary_queries(survey: SalarySurvey) -> None:
    assert queries.latest_survey() == survey
    assert queries.survey_languages(survey) == ["Python", "Go"]

    seniority = queries.salary_by_seniority(survey, "Python")
    assert [(row.group, row.responses, row.median) for row in seniority] == [
        ("Junior", 21, 1500),
        ("Middle", 21, 3000),
        ("Senior", 21, 5000),
    ]
    assert (seniority[0].p25, seniority[0].p75) == (1000, 2000)

    experience = queries.salary_by_experience(survey, "Python")
    assert [(row.group, row.responses) for row in experience] == [
        ("< 1", 21),
        ("3–5", 21),
        ("10+", 26),
    ]

    dynamics = queries.salary_dynamics("Python")
    assert [(point.period, point.median) for point in dynamics] == [
        (date(2025, 12, 1), 2000),
        (date(2026, 6, 1), 2700),
    ]


@pytest.mark.usefixtures("market", "vacancies")
def test_dashboard_tables_and_charts(survey: SalarySurvey) -> None:
    dashboard = Dashboard(Filters(), survey=survey, now=NOW)

    assert dashboard.table_names == ("market", "skills", "seniority", "experience", "dynamics")
    market_table = dashboard.table("market")
    assert market_table.rows[1][:5] == ("Python", 1700, 100, -5, 17.0)
    assert market_table.rows[1][5:7] == ("1500–3500", "2000–4000")
    assert dashboard.table("seniority").title == "Python salaries by seniority (June 2026)"
    assert dashboard.table("skills").headers[1] == "Last 7 days"
    assert dashboard.table("dynamics").rows[-1] == ("June 2026", 93, 2700)
    charts = dashboard.charts()
    assert charts["competition"]["labels"] == ["Python", "Golang"]
    assert charts["trend"]["vacancies"] == [100, 100]
    assert charts["experience"]["labels"] == ["< 1", "3–5", "10+"]
    assert charts["dynamics"]["labels"] == ["Dec 2025", "Jun 2026"]


def test_dashboard_without_survey() -> None:
    dashboard = Dashboard(Filters(), survey=None, now=NOW)

    assert dashboard.table("seniority").rows == ()
    assert dashboard.table("experience").title == "Python salaries by experience"
    assert dashboard.charts()["competition"] == {"labels": [], "values": []}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, Filters(language="Python", category="python", days=7)),
        ({"language": "Go", "category": "", "days": "30"}, Filters("Go", "", 30)),
        ({"language": "Go"}, Filters("Go", "python", 7)),
        ({"language": "Cobol"}, Filters("Python", "python", 7)),
    ],
)
def test_filter_form(data: dict[str, str] | None, expected: Filters) -> None:
    form = FilterForm(
        data, languages=["Python", "Go"], categories=[("", "All"), ("python", "Python")]
    )

    assert form.filters() == expected


def test_filter_form_falls_back_to_available_options() -> None:
    form = FilterForm(None, languages=["Go"], categories=[("golang", "Golang")])

    assert form.filters() == Filters(language="Go", category="golang", days=7)
    assert FilterForm(None, languages=[], categories=[]).filters() == Filters("", "", 7)


@pytest.mark.usefixtures("market", "survey", "vacancies")
def test_dashboard_page(client: Client) -> None:
    response = client.get(reverse("analytics:dashboard"), {"language": "Go", "category": "golang"})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Go salaries by seniority (June 2026)" in content
    assert 'id="chart-data"' in content
    assert "/analytics/export/market.csv?language=Go&amp;category=golang" in content
    assert "The trend appears after the second one." in content


def test_dashboard_page_without_data(client: Client) -> None:
    response = client.get(reverse("analytics:dashboard"))

    assert response.status_code == 200
    assert "Run capture_market_snapshots to load Djinni statistics." in response.content.decode()


def test_root_redirects_to_dashboard(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == reverse("analytics:dashboard")


@pytest.mark.usefixtures("survey")
def test_csv_export(client: Client) -> None:
    url = reverse("analytics:export", kwargs={"name": "seniority", "extension": "csv"})

    response = client.get(url, {"language": "Python"})

    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == 'attachment; filename="jobpulse-seniority.csv"'
    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[0] == "Seniority,Responses,25th percentile,Median,75th percentile"
    assert lines[1] == "Junior,21,1000,1500,2000"


@pytest.mark.usefixtures("market")
def test_xlsx_export(client: Client) -> None:
    url = reverse("analytics:export", kwargs={"name": "market", "extension": "xlsx"})

    response = client.get(url)

    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["Market"]
    assert sheet["A1"].value == "Category"
    assert sheet["A1"].font.bold
    assert sheet["A2"].value == "All categories"
    assert sheet["B3"].value == 1700
    assert sheet.freeze_panes == "A2"


def test_export_unknown_table(client: Client) -> None:
    url = reverse("analytics:export", kwargs={"name": "unknown", "extension": "csv"})

    assert client.get(url).status_code == 404
