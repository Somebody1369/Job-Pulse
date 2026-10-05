from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries
from rest_framework.test import APIClient

from market.models import MarketSnapshot, SalaryResponse, SalarySurvey
from subscriptions.models import Delivery, Subscriber, Subscription
from tests.utils import make_ingestor, make_vacancy_data
from vacancies.models import Skill, Source, Vacancy
from vacancies.salary import SalaryRange

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"


def create_user(username: str, *, bot: bool) -> AbstractBaseUser:
    user = get_user_model().objects.create_user(username=username, password=PASSWORD)
    if bot:
        user.user_permissions.add(Permission.objects.get(codename="access_bot_api"))
    return user


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def bot(api: APIClient) -> APIClient:
    api.force_authenticate(create_user("telegram-bot", bot=True))
    return api


@pytest.fixture
def vacancies() -> dict[str, Vacancy]:
    now = timezone.now()
    dou = Source.objects.get(code="dou")
    djinni = Source.objects.get(code="djinni")
    make_ingestor(dou).ingest(
        [
            make_vacancy_data(
                external_id="1",
                title="Senior Django Developer",
                company="Acme",
                description="Django, PostgreSQL and Celery.",
                is_remote=True,
                salary=SalaryRange(4000, 5000, "USD"),
                published_at=now - timedelta(hours=2),
            ),
            make_vacancy_data(
                external_id="2",
                title="Go Engineer",
                company="Globex",
                categories=frozenset({"Golang"}),
                description="Go, Kafka and Kubernetes.",
                is_remote=False,
                salary=SalaryRange(1500, 2000, "USD"),
                published_at=now - timedelta(hours=5),
            ),
            make_vacancy_data(
                external_id="3",
                title="Python Developer",
                company="Initech",
                description="FastAPI and Django REST Framework.",
                is_remote=True,
                published_at=now - timedelta(days=10),
            ),
        ]
    )
    make_ingestor(djinni).ingest(
        [
            make_vacancy_data(
                external_id="9",
                title="Senior Django Developer",
                company="Acme",
                description="Django and PostgreSQL.",
                is_remote=True,
                published_at=now - timedelta(hours=1),
            )
        ]
    )
    Vacancy.objects.filter(external_id="3").update(experience_months=60, english_level="C1")
    return {vacancy.external_id: vacancy for vacancy in Vacancy.objects.all()}


def titles(response: Any) -> list[str]:
    return [item["title"] for item in response.json()["results"]]


@pytest.mark.usefixtures("vacancies")
def test_vacancy_list_is_paginated_and_avoids_n_plus_one(
    api: APIClient, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_max_num_queries(3):
        response = api.get("/api/v1/vacancies/", {"page_size": 2})

    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 4
    assert len(payload["results"]) == 2
    assert payload["next"].endswith("page=2&page_size=2")
    first = payload["results"][0]
    assert first["board"] == "djinni"
    assert first["company"] == {"name": "Acme", "slug": "acme", "website": ""}
    assert "description" not in first


@pytest.mark.usefixtures("vacancies")
@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"skills": "django,postgresql"}, ["Senior Django Developer", "Senior Django Developer"]),
        ({"skills": "go"}, ["Go Engineer"]),
        ({"source": "dou", "remote": "true"}, ["Senior Django Developer", "Python Developer"]),
        ({"company": "globex"}, ["Go Engineer"]),
        ({"category": "Golang"}, ["Go Engineer"]),
        ({"english_level": "C1"}, ["Python Developer"]),
        ({"min_salary_usd": 3000}, ["Senior Django Developer"]),
        ({"q": "kafka"}, ["Go Engineer"]),
        (
            {"q": "   "},
            [
                "Senior Django Developer",
                "Senior Django Developer",
                "Go Engineer",
                "Python Developer",
            ],
        ),
        (
            {"ordering": "salary_min_usd", "source": "dou", "min_salary_usd": 1},
            ["Go Engineer", "Senior Django Developer"],
        ),
    ],
)
def test_vacancy_filters(api: APIClient, params: dict[str, Any], expected: list[str]) -> None:
    response = api.get("/api/v1/vacancies/", params)

    assert response.status_code == 200
    assert titles(response) == expected


def test_vacancy_published_after_and_detail(api: APIClient, vacancies: dict[str, Vacancy]) -> None:
    since = (timezone.now() - timedelta(days=1)).isoformat()

    recent = api.get("/api/v1/vacancies/", {"published_after": since})
    detail = api.get(f"/api/v1/vacancies/{vacancies['2'].pk}/")

    assert "Python Developer" not in titles(recent)
    assert detail.json()["description"] == "Go, Kafka and Kubernetes."
    assert detail.json()["salary"] == {
        "text": "1500–2000 USD",
        "min": 1500,
        "max": 2000,
        "currency": "USD",
        "min_usd": 1500,
        "max_usd": 2000,
    }
    assert set(detail.json()["skills"]) == {"Go", "Kafka", "Kubernetes"}


@pytest.mark.usefixtures("vacancies")
def test_skills_and_companies(api: APIClient) -> None:
    skills = api.get("/api/v1/skills/").json()["results"]
    django = api.get("/api/v1/skills/django/").json()
    companies = api.get("/api/v1/companies/", {"search": "glo"}).json()["results"]

    assert skills[0] == {"name": "Django", "slug": "django", "aliases": [], "vacancy_count": 3}
    assert django["vacancy_count"] == 3
    assert companies == [{"name": "Globex", "slug": "globex", "website": ""}]


def test_market_endpoints(api: APIClient) -> None:
    common: dict[str, Any] = {
        "active_candidates": 1000,
        "expected_min": 1000,
        "expected_max": 3000,
        "offers_per_candidate": Decimal("0.4"),
        "vacancies_online": 50,
        "offered_min": 1500,
        "offered_max": 3500,
        "applications_per_vacancy": Decimal("40"),
    }
    MarketSnapshot.objects.create(
        category="python", category_label="Python", calculated_on=date(2026, 10, 3), **common
    )
    MarketSnapshot.objects.create(
        category="python", category_label="Python", calculated_on=date(2026, 10, 4), **common
    )
    MarketSnapshot.objects.create(
        category="", category_label="All categories", calculated_on=date(2026, 10, 4), **common
    )

    history = api.get("/api/v1/market/snapshots/", {"category": "python"}).json()
    overview = api.get("/api/v1/market/overview/").json()

    assert [item["calculated_on"] for item in history["results"]] == ["2026-10-04", "2026-10-03"]
    assert [item["category_label"] for item in overview] == ["All categories", "Python"]
    assert overview[1]["candidates_per_vacancy"] == 20.0


def test_salary_endpoints(api: APIClient) -> None:
    assert api.get("/api/v1/salaries/").status_code == 404

    survey = SalarySurvey.objects.create(
        name="2026_june", period=date(2026, 6, 1), source_url="https://example.com/2026_june.csv"
    )
    SalaryResponse.objects.bulk_create(
        SalaryResponse(
            survey=survey,
            salary_usd=1000 + index * 100,
            experience_years=Decimal(4),
            programming_language="Python",
            seniority="Middle",
        )
        for index in range(21)
    )

    seniority = api.get("/api/v1/salaries/")
    experience = api.get("/api/v1/salaries/", {"language": "Python", "group": "experience"})
    dynamics = api.get("/api/v1/salaries/dynamics/", {"language": "Python"})

    assert seniority.json() == [
        {"group": "Middle", "responses": 21, "p25": 1500, "median": 2000, "p75": 2500}
    ]
    assert experience.json()[0]["group"] == "3–5"
    assert dynamics.json() == [{"period": "2026-06-01", "responses": 21, "median": 2000}]
    assert api.get("/api/v1/salaries/", {"group": "age"}).status_code == 400


@pytest.mark.usefixtures("vacancies")
def test_skill_demand_endpoint(api: APIClient) -> None:
    response = api.get("/api/v1/skills/demand/", {"days": 7})

    assert {"skill": "Celery", "current": 1, "previous": 0, "change": 1} in response.json()
    assert {"skill": "Django", "current": 1, "previous": 1, "change": 0} in response.json()
    assert api.get("/api/v1/skills/demand/", {"days": 3}).status_code == 400


def test_jwt_authentication_flow(api: APIClient) -> None:
    create_user("telegram-bot", bot=True)

    tokens = api.post(
        "/api/v1/auth/token/", {"username": "telegram-bot", "password": PASSWORD}, format="json"
    ).json()
    refreshed = api.post(
        "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json"
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.json()['access']}")

    assert api.get("/api/v1/notifications/").status_code == 200


def test_bot_endpoints_require_bot_permission(api: APIClient) -> None:
    assert api.get("/api/v1/notifications/").status_code == 401

    api.force_authenticate(create_user("someone", bot=False))

    assert api.get("/api/v1/notifications/").status_code == 403
    assert api.post("/api/v1/subscribers/", {"chat_id": 1}, format="json").status_code == 403


def test_subscriber_lifecycle(bot: APIClient) -> None:
    created = bot.post("/api/v1/subscribers/", {"chat_id": 42, "username": "anna"}, format="json")
    updated = bot.post("/api/v1/subscribers/", {"chat_id": 42, "username": "anna_k"}, format="json")
    subscription = bot.post(
        "/api/v1/subscribers/42/subscriptions/", {"skills": ["python"]}, format="json"
    )

    assert created.status_code == 201
    assert updated.status_code == 200
    assert bot.get("/api/v1/subscribers/42/").json()["username"] == "anna_k"
    assert subscription.status_code == 201
    assert bot.delete("/api/v1/subscribers/42/").status_code == 204
    assert not Subscription.objects.exists()
    assert bot.get("/api/v1/subscribers/42/").status_code == 404


def test_subscription_management(bot: APIClient) -> None:
    Subscriber.objects.create(chat_id=42)
    Subscriber.objects.create(chat_id=7)
    url = "/api/v1/subscribers/42/subscriptions/"

    created = bot.post(
        url,
        {"skills": ["django", "postgresql"], "remote_only": True, "min_salary_usd": 3000},
        format="json",
    ).json()
    detail = f"{url}{created['id']}/"

    assert created["skills"] == ["django", "postgresql"]
    assert bot.post(url, {"skills": ["cobol"]}, format="json").status_code == 400
    assert bot.patch(detail, {"is_active": False}, format="json").json()["is_active"] is False
    assert len(bot.get(url).json()) == 1
    assert bot.get(f"/api/v1/subscribers/7/subscriptions/{created['id']}/").status_code == 404
    assert bot.post("/api/v1/subscribers/99/subscriptions/", {}, format="json").status_code == 404
    assert bot.delete(detail).status_code == 204


def subscribe(chat_id: int, **fields: Any) -> Subscription:
    subscriber, _ = Subscriber.objects.get_or_create(chat_id=chat_id)
    skills = fields.pop("skills", [])
    subscription = Subscription.objects.create(subscriber=subscriber, **fields)
    subscription.skills.set(skills)
    return subscription


def pending(bot: APIClient, **params: Any) -> list[tuple[int, str, str]]:
    return [
        (item["chat_id"], item["vacancy"]["title"], item["vacancy"]["board"])
        for item in bot.get("/api/v1/notifications/", params).json()
    ]


@pytest.mark.usefixtures("vacancies")
def test_notifications_follow_subscription_rules(bot: APIClient) -> None:
    django = Skill.objects.get(slug="django")
    go = Skill.objects.get(slug="go")
    subscribe(1, skills=[django])
    subscribe(2, skills=[go], remote_only=True)
    subscribe(3, min_salary_usd=3000)
    subscribe(4, max_experience_years=3)
    subscribe(5, is_active=False)

    notifications = pending(bot)

    assert (1, "Senior Django Developer", "djinni") in notifications
    assert [item for item in notifications if item[0] == 1] == [
        (1, "Senior Django Developer", "djinni")
    ]
    assert not [item for item in notifications if item[0] in {2, 5}]
    assert {item[1] for item in notifications if item[0] == 3} == {"Senior Django Developer"}
    assert {item[1] for item in notifications if item[0] == 4} == {
        "Senior Django Developer",
        "Go Engineer",
    }


@pytest.mark.usefixtures("vacancies")
def test_acknowledged_notifications_are_not_repeated(bot: APIClient) -> None:
    subscription = subscribe(1)
    first = bot.get("/api/v1/notifications/", {"limit": 1}).json()
    deliveries = [{"subscription": subscription.pk, "vacancy": first[0]["vacancy"]["id"]}]

    assert (
        bot.post("/api/v1/notifications/", {"deliveries": deliveries}, format="json").status_code
        == 204
    )
    assert (
        bot.post("/api/v1/notifications/", {"deliveries": deliveries}, format="json").status_code
        == 204
    )
    assert Delivery.objects.count() == 1
    assert [title for _, title, _ in pending(bot)] == ["Go Engineer"]
    assert bot.post("/api/v1/notifications/", {"deliveries": []}, format="json").status_code == 400


def test_old_vacancies_are_outside_the_notification_window(bot: APIClient) -> None:
    make_ingestor(Source.objects.get(code="dou")).ingest(
        [make_vacancy_data(published_at=datetime(2020, 1, 1, tzinfo=UTC))]
    )
    subscribe(1)

    assert pending(bot) == []


def test_schema_and_docs(client: Client) -> None:
    assert client.get(reverse("api:schema")).status_code == 200
    assert client.get(reverse("api:docs")).status_code == 200


def test_create_bot_account_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_API_PASSWORD", raising=False)
    generated = StringIO()
    call_command("create_bot_account", stdout=generated)
    monkeypatch.setenv("BOT_API_PASSWORD", PASSWORD)
    updated = StringIO()
    call_command("create_bot_account", stdout=updated)

    user = get_user_model().objects.get(username="telegram-bot")
    assert "Created bot account 'telegram-bot'" in generated.getvalue()
    assert "Generated password: " in generated.getvalue()
    assert "Updated bot account" in updated.getvalue()
    assert "Generated password" not in updated.getvalue()
    assert user.check_password(PASSWORD)
    assert user.has_perm("subscriptions.access_bot_api")


@pytest.mark.parametrize("model", ["subscriber", "delivery"])
def test_subscription_admin_renders(admin_client: Client, model: str) -> None:
    subscribe(1)

    assert admin_client.get(reverse(f"admin:subscriptions_{model}_changelist")).status_code == 200
    assert (
        admin_client.get(
            reverse("admin:subscriptions_subscriber_change", args=[Subscriber.objects.get().pk])
        ).status_code
        == 200
    )


def test_string_representations() -> None:
    subscription = subscribe(1)
    named = Subscriber.objects.create(chat_id=2, username="anna")
    make_ingestor(Source.objects.get(code="dou")).ingest([make_vacancy_data()])
    delivery = Delivery.objects.create(subscription=subscription, vacancy=Vacancy.objects.get())

    assert str(subscription) == f"Subscription #{subscription.pk} of 1"
    assert str(named) == "@anna"
    assert str(delivery) == "Python Developer to 1"
