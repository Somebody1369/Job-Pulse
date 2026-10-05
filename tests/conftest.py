from collections.abc import Iterator

import pytest
import responses
from pytest_django.fixtures import Settings

from core.http import HttpClient


@pytest.fixture(autouse=True)
def _test_settings(settings: Settings) -> None:
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.WHITENOISE_AUTOREFRESH = True
    settings.SCRAPER_MIN_INTERVAL = 0
    settings.SCRAPER_MAX_RETRIES = 0


@pytest.fixture
def http_client() -> Iterator[HttpClient]:
    with HttpClient(
        user_agent="JobPulseTest/1.0",
        timeout=(1.0, 1.0),
        max_retries=0,
        backoff_factor=0,
        min_interval=0,
    ) as client:
        yield client


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock() as mock:
        yield mock
