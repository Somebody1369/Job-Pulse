import pytest
import requests
import responses

from core.http import HttpClient
from core.robots import RobotsPolicy

ROBOTS_URL = "https://jobs.example.com/robots.txt"
USER_AGENT = "JobPulse/0.1 (+mailto:team@example.com)"


@pytest.fixture
def policy(http_client: HttpClient) -> RobotsPolicy:
    return RobotsPolicy(http_client, USER_AGENT)


def test_respects_disallow_rules_and_caches_robots(
    policy: RobotsPolicy, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(ROBOTS_URL, body="User-agent: *\nDisallow: /developers\n")

    assert policy.is_allowed("https://jobs.example.com/jobs/1-python-developer/")
    assert not policy.is_allowed("https://jobs.example.com/developers/42/")
    assert len(mocked_responses.calls) == 1


def test_applies_rules_for_matching_user_agent(
    policy: RobotsPolicy, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(ROBOTS_URL, body="User-agent: JobPulse\nDisallow: /\n")

    assert not policy.is_allowed("https://jobs.example.com/jobs/1/")


@pytest.mark.parametrize(
    ("response", "allowed"),
    [
        ({"status": 404}, True),
        ({"status": 503}, False),
        ({"body": requests.ConnectionError("unreachable")}, False),
    ],
)
def test_handles_unavailable_robots(
    policy: RobotsPolicy,
    mocked_responses: responses.RequestsMock,
    response: dict[str, object],
    allowed: bool,
) -> None:
    mocked_responses.get(ROBOTS_URL, **response)

    assert policy.is_allowed("https://jobs.example.com/jobs/1/") is allowed
