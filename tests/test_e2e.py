from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_django.live_server_helper import LiveServer
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from market.models import MarketSnapshot, SalaryResponse, SalarySurvey

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True, serialized_rollback=True)]

WAIT_SECONDS = 10


@pytest.fixture
def browser() -> Iterator[Chrome]:
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,1600")
    driver = Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def market_data() -> None:
    snapshot: dict[str, Any] = {
        "calculated_on": date(2026, 10, 4),
        "expected_min": 1500,
        "expected_max": 3500,
        "offers_per_candidate": Decimal("0.4"),
        "vacancies_online": 100,
        "offered_min": 2000,
        "offered_max": 4000,
        "applications_per_vacancy": Decimal("40"),
    }
    MarketSnapshot.objects.create(
        category="python", category_label="Python", active_candidates=1700, **snapshot
    )
    MarketSnapshot.objects.create(
        category="golang", category_label="Golang", active_candidates=300, **snapshot
    )
    survey = SalarySurvey.objects.create(
        name="2026_june", period=date(2026, 6, 1), source_url="https://example.com/2026_june.csv"
    )
    SalaryResponse.objects.bulk_create(
        SalaryResponse(
            survey=survey,
            salary_usd=1000 + index * 100,
            experience_years=Decimal(index % 12),
            programming_language=language,
            seniority=seniority,
        )
        for language in ("Python", "Go")
        for seniority in ("Junior", "Middle", "Senior")
        for index in range(25)
    )


def heading_texts(browser: Chrome) -> list[str]:
    return [heading.text for heading in browser.find_elements(By.CSS_SELECTOR, "h2")]


@pytest.mark.usefixtures("market_data")
def test_dashboard_filters_reload_tables_and_draw_charts(
    browser: Chrome, live_server: LiveServer
) -> None:
    wait = WebDriverWait(browser, WAIT_SECONDS)
    browser.get(f"{live_server.url}/analytics/")

    wait.until(expected_conditions.presence_of_element_located((By.ID, "competition-chart")))
    assert "Python salaries by seniority (June 2026)" in heading_texts(browser)
    assert browser.execute_script("return typeof window.Chart") == "function"
    assert (
        browser.execute_script(
            "return document.getElementById('competition-chart').getBoundingClientRect().height"
        )
        > 0
    )

    Select(browser.find_element(By.NAME, "language")).select_by_value("Go")

    wait.until(expected_conditions.url_contains("language=Go"))
    wait.until(
        expected_conditions.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "#table-seniority h2"), "Go salaries by seniority"
        )
    )
    rows = browser.find_elements(By.CSS_SELECTOR, "#table-seniority tbody tr")
    assert [row.find_element(By.TAG_NAME, "td").text for row in rows] == [
        "Junior",
        "Middle",
        "Senior",
    ]
    export = browser.find_element(By.LINK_TEXT, "Excel")
    assert "language=Go" in (export.get_attribute("href") or "")
