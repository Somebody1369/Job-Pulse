from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from bot.models import (
    MarketSnapshot,
    Notification,
    SalaryRow,
    Skill,
    Subscription,
    SubscriptionDraft,
    Vacancy,
)

CHAT_ID = 1001


def make_vacancy(**overrides: Any) -> Vacancy:
    values: dict[str, Any] = {
        "id": 7,
        "title": "Senior Python Developer",
        "url": "https://djinni.co/jobs/7-senior-python-developer/",
        "board": "djinni",
        "company": "Acme",
        "locations": (),
        "is_remote": True,
        "salary_text": "4000–5000 USD",
        "skills": ("Python", "Django"),
    }
    return Vacancy(**(values | overrides))


def make_snapshot(**overrides: Any) -> MarketSnapshot:
    values: dict[str, Any] = {
        "category": "python",
        "label": "Python",
        "candidates": 1716,
        "vacancies": 120,
        "vacancies_change": -17,
        "candidates_per_vacancy": 14.3,
        "expected": (1000, 3800),
        "offered": (2000, 3800),
    }
    return MarketSnapshot(**(values | overrides))


@dataclass
class FakeApi:
    skills_list: list[Skill] = field(
        default_factory=lambda: [Skill("Python", "python"), Skill("Django", "django")]
    )
    subscription_list: list[Subscription] = field(default_factory=list)
    vacancies: list[Vacancy] = field(default_factory=list)
    snapshots: list[MarketSnapshot] = field(default_factory=list)
    salary_rows: list[SalaryRow] = field(default_factory=list)
    report: bytes | None = None
    pending: list[Notification] = field(default_factory=list)
    weekly: dict[int, bool] = field(default_factory=dict)
    calls: list[tuple[str, Any]] = field(default_factory=list)

    async def register(self, chat_id: int, username: str) -> None:
        self.calls.append(("register", (chat_id, username)))

    async def forget(self, chat_id: int) -> None:
        self.calls.append(("forget", chat_id))

    async def weekly_report_enabled(self, chat_id: int) -> bool:
        return self.weekly.get(chat_id, False)

    async def set_weekly_report(self, chat_id: int, *, enabled: bool) -> None:
        self.weekly[chat_id] = enabled

    async def weekly_report_subscribers(self) -> list[int]:
        return [chat_id for chat_id, enabled in self.weekly.items() if enabled]

    async def skills(self, *, limit: int) -> list[Skill]:
        return self.skills_list[:limit]

    async def subscriptions(self, chat_id: int) -> list[Subscription]:
        self.calls.append(("subscriptions", chat_id))
        return self.subscription_list

    async def create_subscription(self, chat_id: int, draft: SubscriptionDraft) -> Subscription:
        self.calls.append(("create_subscription", (chat_id, draft)))
        return Subscription(
            id=1,
            skills=draft.skills,
            remote_only=draft.remote_only,
            min_salary_usd=draft.min_salary_usd,
            max_experience_years=draft.max_experience_years,
            is_active=True,
        )

    async def set_subscription_active(
        self, chat_id: int, subscription_id: int, *, active: bool
    ) -> Subscription:
        self.calls.append(("set_active", (chat_id, subscription_id, active)))
        return replace(self.subscription_list[0], is_active=active)

    async def delete_subscription(self, chat_id: int, subscription_id: int) -> None:
        self.calls.append(("delete_subscription", (chat_id, subscription_id)))

    async def search(self, text: str, *, limit: int) -> list[Vacancy]:
        self.calls.append(("search", text))
        return self.vacancies[:limit]

    async def market_overview(self) -> list[MarketSnapshot]:
        return self.snapshots

    async def salaries(self, language: str, *, group: str) -> list[SalaryRow]:
        self.calls.append(("salaries", (language, group)))
        return self.salary_rows

    async def latest_report(self) -> bytes | None:
        return self.report

    async def notifications(self, *, limit: int) -> list[Notification]:
        self.calls.append(("notifications", limit))
        return self.pending

    async def acknowledge(self, deliveries: Iterable[tuple[int, int]]) -> None:
        self.calls.append(("acknowledge", list(deliveries)))


def fake_message(username: str | None = "anna") -> MagicMock:
    message = MagicMock(spec=Message)
    message.chat = MagicMock(id=CHAT_ID)
    message.from_user = MagicMock(username=username)
    message.answer = AsyncMock()
    message.answer_photo = AsyncMock()
    message.edit_text = AsyncMock()
    message.edit_reply_markup = AsyncMock()
    return message


def fake_callback(message: MagicMock | None = None) -> MagicMock:
    callback = MagicMock(spec=CallbackQuery)
    callback.message = message if message is not None else fake_message()
    callback.from_user = MagicMock(id=CHAT_ID, username="anna")
    callback.answer = AsyncMock()
    return callback


def fsm_context() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=CHAT_ID, user_id=CHAT_ID)
    )
