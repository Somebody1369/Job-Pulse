from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
import responses
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse
from pytest_django.fixtures import Settings
from responses import matchers

from core.http import HttpClient
from market.djinni import (
    DJINNI_SALARIES_URL,
    DjinniMarketClient,
    MarketPageError,
    MarketStats,
    parse_market_page,
)
from market.models import MarketSnapshot
from market.services import capture_market_snapshots
from market.tasks import capture_market_snapshots as capture_market_snapshots_task
from tests.utils import DenyList, read_fixture

ROBOTS_URL = "https://djinni.co/robots.txt"


def market_page(name: str) -> str:
    return read_fixture(f"djinni_market_{name}.html").decode()


def mock_market(mock: responses.RequestsMock, category: str, page: str) -> None:
    params = {"category": category} if category else {}
    mock.get(
        DJINNI_SALARIES_URL,
        body=market_page(page),
        match=[matchers.query_param_matcher(params)],
    )


def test_parse_market_page_for_category() -> None:
    stats = parse_market_page(market_page("python"), "python")

    assert stats == MarketStats(
        category="python",
        category_label="Python",
        calculated_on=date(2026, 10, 4),
        active_candidates=1716,
        expected_min=1000,
        expected_max=3800,
        offers_per_candidate=Decimal("0.5"),
        vacancies_online=120,
        vacancies_change=-17,
        offered_min=2000,
        offered_max=3800,
        applications_per_vacancy=Decimal("104.5"),
        djinni_index=Decimal("0.17"),
        offers_30d=1834,
        applications_30d=11068,
    )


def test_parse_market_page_with_growing_vacancies() -> None:
    stats = parse_market_page(market_page("golang"), "golang")

    assert stats.category_label == "Golang"
    assert stats.vacancies_change == 12


def test_parse_market_page_for_whole_market() -> None:
    stats = parse_market_page(market_page("all"), "")

    assert stats.category_label == "All categories"
    assert stats.active_candidates == 42822


@pytest.mark.parametrize(("page", "category"), [("all", "devops"), ("python", "")])
def test_parse_market_page_rejects_unrecognized_category(page: str, category: str) -> None:
    with pytest.raises(MarketPageError, match="does not recognize"):
        parse_market_page(market_page(page), category)


@pytest.mark.parametrize(
    ("original", "replacement", "message"),
    [
        ('id="jobs_card"', 'id="other_card"', "#jobs_card"),
        ("Середня вилка", "Медіана", "середня вилка"),
        ('<span class="fs-1" data-format="int">\n        1716', '<span class="fs-1">n/a', "number"),
        ("            104.5", "            n/a", "decimal"),
        ('class="fs-1"', 'class="fs-2"', "headline"),
        ('<span data-format="int">1000</span>', "1000", "salary range"),
        ('data-calculated-at="2026-10-04T20:00:42.235254"', "", "calculation date"),
    ],
)
def test_parse_market_page_reports_layout_changes(
    original: str, replacement: str, message: str
) -> None:
    markup = market_page("python")
    assert original in markup

    with pytest.raises(MarketPageError, match=message):
        parse_market_page(markup.replace(original, replacement, 1), "python")


def test_parse_market_page_without_index_card() -> None:
    markup = market_page("python").replace('id="djinni_index_card"', 'id="removed_card"')

    stats = parse_market_page(markup, "python")

    assert (stats.djinni_index, stats.offers_30d, stats.applications_30d) == (None, None, None)


def test_parse_market_page_without_vacancy_change() -> None:
    markup = market_page("python").replace('class="text-diff text-danger"', 'class="text-danger"')

    assert parse_market_page(markup, "python").vacancies_change is None


def test_client_respects_robots(http_client: HttpClient) -> None:
    client = DjinniMarketClient(http_client, DenyList(DJINNI_SALARIES_URL))

    with pytest.raises(MarketPageError, match=r"robots\.txt"):
        client.fetch("python")


@pytest.mark.django_db
def test_capture_market_snapshots_upserts_daily_snapshots(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(ROBOTS_URL, body="User-agent: *\nDisallow: /developers\n")
    mock_market(mocked_responses, "python", "python")
    mock_market(mocked_responses, "", "all")
    mock_market(mocked_responses, "devops", "all")
    mocked_responses.get(
        DJINNI_SALARIES_URL, status=503, match=[matchers.query_param_matcher({"category": "go"})]
    )

    first = capture_market_snapshots(http_client, ["python", "", "devops", "go"])
    second = capture_market_snapshots(http_client, ["python"])

    assert [snapshot.category_label for snapshot in first.captured] == ["Python", "All categories"]
    assert first.failed == ["devops", "go"]
    assert second.failed == []
    assert MarketSnapshot.objects.count() == 2
    python = MarketSnapshot.objects.get(category="python")
    assert python.candidates_per_vacancy == 14.3
    assert str(python) == "Python on 2026-10-04"


def test_candidates_per_vacancy_without_vacancies() -> None:
    assert MarketSnapshot(active_candidates=10, vacancies_online=0).candidates_per_vacancy is None


@pytest.mark.django_db
def test_capture_market_snapshots_command(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(ROBOTS_URL, body="")
    mock_market(mocked_responses, "golang", "golang")
    output = StringIO()

    call_command("capture_market_snapshots", "-c", "golang", stdout=output)

    assert "Golang: 315 candidates, 42 vacancies" in output.getvalue()
    assert "Captured 1 snapshots" in output.getvalue()


@pytest.mark.django_db
def test_capture_market_snapshots_command_reports_failures(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(ROBOTS_URL, body="")
    mock_market(mocked_responses, "devops", "all")

    with pytest.raises(CommandError, match="Failed categories: 'devops'"):
        call_command("capture_market_snapshots", "-c", "devops", stdout=StringIO())


@pytest.mark.django_db
def test_capture_market_snapshots_task(
    settings: Settings, mocked_responses: responses.RequestsMock
) -> None:
    settings.MARKET_CATEGORIES = ["python"]
    mocked_responses.get(ROBOTS_URL, body="")
    mock_market(mocked_responses, "python", "python")

    assert capture_market_snapshots_task() == {"captured": 1, "failed": 0}


@pytest.mark.django_db
def test_market_snapshot_admin_renders(admin_client: Client) -> None:
    response = admin_client.get(reverse("admin:market_marketsnapshot_changelist"))

    assert response.status_code == 200
