from collections.abc import Iterator

import pytest
import responses
from django.conf import settings as django_settings
from django.core.cache import cache
from pytest_django.fixtures import Settings

from core.http import HttpClient


def pytest_configure() -> None:
    django_settings.STORAGES = {
        **django_settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    django_settings.WHITENOISE_AUTOREFRESH = True


@pytest.fixture(autouse=True)
def _test_settings(settings: Settings) -> None:
    cache.clear()
    settings.SCRAPER_MIN_INTERVAL = 0
    settings.GREENHOUSE_BOARDS = []
    settings.LEVER_BOARDS = []
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
