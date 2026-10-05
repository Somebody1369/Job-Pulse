from collections.abc import Iterator

import httpx
import pytest
import respx

from bot.api import ApiError, JobPulseApi
from bot.config import BotConfig, ConfigError
from bot.models import SubscriptionDraft

BASE_URL = "http://api.test/api/v1/"
TOKEN = {"access": "access-1", "refresh": "refresh-1"}

VACANCY = {
    "id": 3,
    "title": "Go Engineer",
    "url": "https://jobs.dou.ua/companies/globex/vacancies/3/",
    "board": "dou",
    "company": {"name": "Globex", "slug": "globex", "website": ""},
    "locations": ["Київ"],
    "is_remote": False,
    "salary": {
        "text": "",
        "min": None,
        "max": None,
        "currency": "",
        "min_usd": None,
        "max_usd": None,
    },
    "skills": ["Go"],
}


@pytest.fixture
def api() -> JobPulseApi:
    return JobPulseApi(BASE_URL, username="telegram-bot", password="secret")


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.post("auth/token/").respond(json=TOKEN)
        yield mock


def test_config_from_env() -> None:
    config = BotConfig.from_env(
        {"TELEGRAM_BOT_TOKEN": "123:abc", "BOT_API_PASSWORD": "secret", "BOT_NOTIFY_INTERVAL": "60"}
    )

    assert config.api_url == "http://localhost:8000/api/v1/"
    assert config.api_username == "telegram-bot"
    assert config.notify_interval == 60.0


def test_config_requires_secrets() -> None:
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN, BOT_API_PASSWORD"):
        BotConfig.from_env({})


async def test_token_is_reused_and_refreshed_after_401(
    api: JobPulseApi, router: respx.MockRouter
) -> None:
    subscriptions = router.get("subscribers/5/subscriptions/").mock(
        side_effect=[
            httpx.Response(200, json=[]),
            httpx.Response(401),
            httpx.Response(200, json=[]),
        ]
    )

    await api.subscriptions(5)
    await api.subscriptions(5)

    assert router.routes[0].call_count == 2
    assert subscriptions.call_count == 3
    assert subscriptions.calls[0].request.headers["Authorization"] == "Bearer access-1"


async def test_public_requests_do_not_authenticate(
    api: JobPulseApi, router: respx.MockRouter
) -> None:
    search = router.get("vacancies/", params={"q": "go", "page_size": "5"}).respond(
        json={"results": [VACANCY]}
    )

    (vacancy,) = await api.search("go", limit=5)

    assert vacancy.company == "Globex"
    assert vacancy.locations == ("Київ",)
    assert vacancy.salary_text == ""
    assert "Authorization" not in search.calls[0].request.headers
    assert router.routes[0].call_count == 0


async def test_errors_are_reported(api: JobPulseApi, router: respx.MockRouter) -> None:
    router.get("notifications/").respond(500, text="boom")

    with pytest.raises(ApiError, match="500: boom") as error:
        await api.notifications(limit=5)

    assert error.value.status_code == 500


async def test_rejected_credentials(api: JobPulseApi) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("auth/token/").respond(401)

        with pytest.raises(ApiError, match="credentials were rejected"):
            await api.subscriptions(5)


async def test_subscriber_endpoints(api: JobPulseApi, router: respx.MockRouter) -> None:
    register = router.post("subscribers/").respond(201, json={})
    router.get("subscribers/5/").respond(json={"chat_id": 5, "weekly_report": True})
    weekly = router.patch("subscribers/5/").respond(json={})
    forget = router.delete("subscribers/5/").respond(404)
    router.get("subscribers/", params={"weekly_report": "true", "page_size": "100"}).respond(
        json={"results": [{"chat_id": 1}], "next": f"{BASE_URL}subscribers/?page=2"}
    )
    router.get("subscribers/", params={"page": "2"}).respond(
        json={"results": [{"chat_id": 2}], "next": None}
    )

    await api.register(5, "anna")
    enabled = await api.weekly_report_enabled(5)
    await api.set_weekly_report(5, enabled=False)
    await api.forget(5)
    chat_ids = await api.weekly_report_subscribers()

    assert register.calls[0].request.content == b'{"chat_id":5,"username":"anna"}'
    assert enabled is True
    assert weekly.calls[0].request.content == b'{"weekly_report":false}'
    assert forget.called
    assert chat_ids == [1, 2]


async def test_subscription_endpoints(api: JobPulseApi, router: respx.MockRouter) -> None:
    payload = {
        "id": 9,
        "skills": ["python"],
        "remote_only": True,
        "min_salary_usd": 3000,
        "max_experience_years": None,
        "is_active": True,
    }
    create = router.post("subscribers/5/subscriptions/").respond(201, json=payload)
    router.patch("subscribers/5/subscriptions/9/").respond(json=payload | {"is_active": False})
    delete = router.delete("subscribers/5/subscriptions/9/").respond(204)

    created = await api.create_subscription(
        5, SubscriptionDraft(skills=("python",), remote_only=True, min_salary_usd=3000)
    )
    paused = await api.set_subscription_active(5, 9, active=False)
    await api.delete_subscription(5, 9)

    assert created.skills == ("python",)
    assert paused.is_active is False
    assert create.calls[0].request.content == (
        b'{"skills":["python"],"remote_only":true,"min_salary_usd":3000,"max_experience_years":null}'
    )
    assert delete.called


async def test_market_salary_report_and_skill_endpoints(
    api: JobPulseApi, router: respx.MockRouter
) -> None:
    router.get("skills/").respond(json={"results": [{"name": "Python", "slug": "python"}]})
    router.get("market/overview/").respond(
        json=[
            {
                "category": "python",
                "category_label": "Python",
                "active_candidates": 1716,
                "vacancies_online": 120,
                "vacancies_change": -17,
                "candidates_per_vacancy": 14.3,
                "expected_min": 1000,
                "expected_max": 3800,
                "offered_min": 2000,
                "offered_max": 3800,
            }
        ]
    )
    salaries = router.get("salaries/")
    salaries.side_effect = [
        httpx.Response(
            200, json=[{"group": "Middle", "responses": 9, "p25": 1, "median": 2, "p75": 3}]
        ),
        httpx.Response(404),
    ]
    report = router.get("reports/latest/")
    report.side_effect = [httpx.Response(200, content=b"png"), httpx.Response(404)]

    assert (await api.skills(limit=10))[0].slug == "python"
    assert (await api.market_overview())[0].expected == (1000, 3800)
    assert (await api.salaries("Python", group="seniority"))[0].median == 2
    assert await api.salaries("Cobol", group="seniority") == []
    assert await api.latest_report() == b"png"
    assert await api.latest_report() is None


async def test_notifications_and_acknowledgements(
    api: JobPulseApi, router: respx.MockRouter
) -> None:
    router.get("notifications/", params={"limit": "5"}).respond(
        json=[{"subscription": 9, "chat_id": 5, "vacancy": VACANCY}]
    )
    ack = router.post("notifications/").respond(204)

    (notification,) = await api.notifications(limit=5)
    await api.acknowledge([])
    await api.acknowledge([(9, 3)])
    await api.close()

    assert (notification.subscription_id, notification.chat_id) == (9, 5)
    assert notification.vacancy.title == "Go Engineer"
    assert ack.call_count == 1
    assert ack.calls[0].request.content == b'{"deliveries":[{"subscription":9,"vacancy":3}]}'
