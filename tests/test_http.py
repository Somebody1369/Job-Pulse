import pytest
import requests
import responses
from pytest_django.fixtures import Settings
from responses import matchers

from core.http import HttpClient

URL = "https://example.com/feed"
OTHER_HOST_URL = "https://other.example.com/feed"


def test_get_sends_user_agent_and_params(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        URL,
        body="ok",
        match=[
            matchers.query_param_matcher({"category": "Python"}),
            matchers.header_matcher({"User-Agent": "JobPulseTest/1.0"}),
        ],
    )

    assert http_client.get(URL, params={"category": "Python"}).text == "ok"


def test_get_raises_for_error_status(
    http_client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(URL, status=404)

    with pytest.raises(requests.HTTPError):
        http_client.get(URL)


def test_get_waits_between_requests_to_the_same_host(
    mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("core.http.time.sleep", sleeps.append)
    mocked_responses.get(URL)
    mocked_responses.get(OTHER_HOST_URL)

    with HttpClient(
        user_agent="JobPulseTest/1.0",
        timeout=(1.0, 1.0),
        max_retries=0,
        backoff_factor=0,
        min_interval=30.0,
    ) as client:
        client.get(URL)
        client.get(OTHER_HOST_URL)
        client.get(URL)

    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= 30.0


def test_from_settings_uses_configured_user_agent(
    settings: Settings, mocked_responses: responses.RequestsMock
) -> None:
    settings.SCRAPER_USER_AGENT = "JobPulse/2.0 (+mailto:team@example.com)"
    mocked_responses.get(
        URL,
        match=[matchers.header_matcher({"User-Agent": "JobPulse/2.0 (+mailto:team@example.com)"})],
    )

    with HttpClient.from_settings() as client:
        assert client.get(URL).status_code == 200
