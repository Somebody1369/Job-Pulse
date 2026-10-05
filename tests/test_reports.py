from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from pytest_django.fixtures import Settings
from pytest_django.live_server_helper import LiveServer
from rest_framework.test import APIClient

from analytics import reports
from analytics.models import DashboardReport
from analytics.reports import BrowserConfig, capture_page, render_dashboard_report
from analytics.tasks import render_dashboard_report as render_dashboard_report_task

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def fake_capture(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, BrowserConfig]]:
    calls: list[tuple[str, BrowserConfig]] = []

    def capture(url: str, config: BrowserConfig) -> bytes:
        calls.append((url, config))
        return PNG_SIGNATURE + bytes(len(calls))

    monkeypatch.setattr(reports, "capture_page", capture)
    return calls


def test_browser_config_from_settings(settings: Settings) -> None:
    settings.REPORT_CHROME_BINARY = "/usr/bin/chromium"
    settings.REPORT_CHROMEDRIVER = "/usr/bin/chromedriver"
    settings.REPORT_CHROME_ARGUMENTS = ["--no-sandbox"]

    config = BrowserConfig.from_settings()
    options = config.options()

    assert options.binary_location == "/usr/bin/chromium"
    assert "--no-sandbox" in options.arguments
    assert "--headless=new" in options.arguments
    assert "--window-size=1280,1600" in options.arguments
    assert config.service().path == "/usr/bin/chromedriver"


@pytest.mark.django_db
def test_render_dashboard_report_keeps_recent_history(
    settings: Settings, fake_capture: list[tuple[str, BrowserConfig]]
) -> None:
    settings.REPORT_HISTORY_SIZE = 2
    settings.REPORT_DASHBOARD_URL = "http://web:8000/analytics/"

    for _ in range(3):
        render_dashboard_report()

    latest = DashboardReport.objects.first()
    assert latest is not None
    assert DashboardReport.objects.count() == 2
    assert bytes(latest.image) == PNG_SIGNATURE + bytes(3)
    assert fake_capture[0][0] == "http://web:8000/analytics/"


@pytest.mark.django_db
@pytest.mark.usefixtures("fake_capture")
def test_report_command_task_and_admin(admin_client: Client) -> None:
    output = StringIO()

    call_command("render_dashboard_report", stdout=output)
    report_id = render_dashboard_report_task()

    assert "Saved Dashboard report" in output.getvalue()
    assert DashboardReport.objects.filter(pk=report_id).exists()
    assert (
        admin_client.get(reverse("admin:analytics_dashboardreport_changelist")).status_code == 200
    )
    assert admin_client.get(reverse("admin:analytics_dashboardreport_add")).status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("fake_capture")
def test_latest_report_endpoint() -> None:
    api = APIClient()
    assert api.get("/api/v1/reports/latest/").status_code == 404

    render_dashboard_report()
    response = api.get("/api/v1/reports/latest/")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content.startswith(PNG_SIGNATURE)
    assert response["Last-Modified"].endswith("GMT")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_capture_page_renders_dashboard_png(live_server: LiveServer) -> None:
    image = capture_page(f"{live_server.url}/analytics/", BrowserConfig(timeout=15))

    assert image.startswith(PNG_SIGNATURE)
    assert len(image) > 10_000
