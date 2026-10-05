from dataclasses import dataclass
from typing import Final, Self

from django.conf import settings
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from analytics.models import DashboardReport

FINISH_ANIMATIONS: Final = (
    "Object.values(window.Chart.instances).forEach((chart) => {"
    " chart.stop(); chart.update('none'); });"
)
CHARTS_READY: Final = (
    "return document.readyState === 'complete' && typeof window.Chart === 'function'"
)
HEADLESS_ARGUMENTS: Final = ("--headless=new", "--hide-scrollbars", "--disable-dev-shm-usage")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrowserConfig:
    binary: str = ""
    driver: str = ""
    arguments: tuple[str, ...] = ()
    window_size: tuple[int, int] = (1280, 1600)
    timeout: float = 30.0

    @classmethod
    def from_settings(cls) -> Self:
        return cls(
            binary=settings.REPORT_CHROME_BINARY,
            driver=settings.REPORT_CHROMEDRIVER,
            arguments=tuple(settings.REPORT_CHROME_ARGUMENTS),
        )

    def options(self) -> ChromeOptions:
        options = ChromeOptions()
        width, height = self.window_size
        for argument in (*HEADLESS_ARGUMENTS, *self.arguments, f"--window-size={width},{height}"):
            options.add_argument(argument)
        if self.binary:
            options.binary_location = self.binary
        return options

    def service(self) -> Service:
        return Service(executable_path=self.driver) if self.driver else Service()


def capture_page(url: str, config: BrowserConfig) -> bytes:
    driver = Chrome(options=config.options(), service=config.service())
    try:
        driver.get(url)
        WebDriverWait(driver, config.timeout).until(_charts_ready)
        driver.execute_script(FINISH_ANIMATIONS)
        return driver.get_screenshot_as_png()
    finally:
        driver.quit()


def render_dashboard_report() -> DashboardReport:
    image = capture_page(settings.REPORT_DASHBOARD_URL, BrowserConfig.from_settings())
    report = DashboardReport.objects.create(image=image)
    stale = DashboardReport.objects.values_list("pk", flat=True)[settings.REPORT_HISTORY_SIZE :]
    DashboardReport.objects.filter(pk__in=list(stale)).delete()
    return report


def _charts_ready(driver: WebDriver) -> bool:
    return bool(driver.execute_script(CHARTS_READY))
