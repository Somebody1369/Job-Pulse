import asyncio
import runpy
from collections.abc import Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from aiogram import Dispatcher
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage, TelegramMethod

from bot import app, scheduling, texts
from bot.api import ApiError
from bot.config import BotConfig
from bot.models import Notification
from bot.notifier import broadcast_weekly_report, deliver_notifications
from tests.bot_fakes import FakeApi, make_vacancy

KYIV = ZoneInfo("Europe/Kyiv")


class StopLoopError(Exception):
    pass


def notification(chat_id: int, vacancy_id: int) -> Notification:
    return Notification(
        subscription_id=chat_id * 10, chat_id=chat_id, vacancy=make_vacancy(id=vacancy_id)
    )


def telegram_error(error_type: type[TelegramAPIError]) -> TelegramAPIError:
    method = cast("TelegramMethod[Any]", SendMessage(chat_id=1, text="x"))
    return error_type(method=method, message="error")


async def test_deliver_notifications_handles_blocked_and_invalid_chats() -> None:
    api = FakeApi(
        pending=[notification(1, 7), notification(2, 8), notification(2, 9), notification(3, 10)]
    )
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=[
            None,
            telegram_error(TelegramForbiddenError),
            telegram_error(TelegramBadRequest),
        ]
    )

    sent = await deliver_notifications(bot, api, limit=5)

    assert sent == 1
    assert ("notifications", 5) in api.calls
    assert ("acknowledge", [(10, 7), (30, 10)]) in api.calls
    assert ("forget", 2) in api.calls
    assert bot.send_message.await_count == 3


async def test_broadcast_weekly_report() -> None:
    bot = MagicMock()
    bot.send_photo = AsyncMock(side_effect=[None, telegram_error(TelegramForbiddenError)])
    api = FakeApi(report=b"png", weekly={1: True, 2: True, 3: False})

    assert await broadcast_weekly_report(bot, FakeApi(weekly={1: True})) == 0
    assert await broadcast_weekly_report(bot, api) == 1
    assert ("forget", 2) in api.calls
    assert bot.send_photo.await_args_list[0].kwargs["caption"] == texts.REPORT_CAPTION


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 5, 9, 30, tzinfo=KYIV), datetime(2026, 10, 5, 10, 0, tzinfo=KYIV)),
        (datetime(2026, 10, 5, 10, 0, tzinfo=KYIV), datetime(2026, 10, 12, 10, 0, tzinfo=KYIV)),
        (datetime(2026, 10, 8, 18, 0, tzinfo=KYIV), datetime(2026, 10, 12, 10, 0, tzinfo=KYIV)),
    ],
)
def test_next_weekly_run(now: datetime, expected: datetime) -> None:
    assert scheduling.next_weekly_run(now, weekday=0, hour=10) == expected


async def test_run_job_logs_failures(caplog: pytest.LogCaptureFixture) -> None:
    await scheduling.run_job("broken", AsyncMock(side_effect=RuntimeError("boom")))

    assert "Scheduled job broken failed" in caplog.text


async def test_run_every_repeats_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job = AsyncMock()
    monkeypatch.setattr(
        "bot.scheduling.asyncio.sleep", AsyncMock(side_effect=[None, StopLoopError])
    )

    with pytest.raises(StopLoopError):
        await scheduling.run_every("notifications", 60, job)

    assert job.await_count == 2


async def test_run_weekly_waits_for_next_run(monkeypatch: pytest.MonkeyPatch) -> None:
    job = AsyncMock()
    sleep = AsyncMock(side_effect=[None, StopLoopError])
    monkeypatch.setattr("bot.scheduling.asyncio.sleep", sleep)

    with pytest.raises(StopLoopError):
        await scheduling.run_weekly("weekly", weekday=0, hour=10, zone=KYIV, job=job)

    assert job.await_count == 1
    assert 0 < sleep.await_args_list[0].args[0] <= 7 * 24 * 3600


def test_build_dispatcher() -> None:
    api = FakeApi()

    dispatcher = app.build_dispatcher(api, MemoryStorage())

    assert isinstance(dispatcher, Dispatcher)
    assert dispatcher.workflow_data["api"] is api
    assert [router.name for router in dispatcher.sub_routers] == [
        "common",
        "subscriptions",
        "market",
    ]
    assert [command.command for command in app.bot_commands()][:2] == ["subscribe", "subscriptions"]


async def test_api_errors_are_reported_to_the_user() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    callback = MagicMock()
    callback.answer = AsyncMock()
    exception = ApiError(503, "down")

    message_event = MagicMock(exception=exception)
    message_event.update.message = message
    callback_event = MagicMock(exception=exception)
    callback_event.update.message = None
    callback_event.update.callback_query = callback

    assert await app.handle_api_error(message_event) is True
    assert await app.handle_api_error(callback_event) is True
    message.answer.assert_awaited_once_with(texts.SERVICE_UNAVAILABLE)
    callback.answer.assert_awaited_once_with(texts.SERVICE_UNAVAILABLE, show_alert=True)


@pytest.mark.parametrize("redis_url", ["", "redis://localhost:6379/1"])
async def test_run_starts_polling_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, redis_url: str
) -> None:
    polling = AsyncMock()
    commands = AsyncMock()
    monkeypatch.setattr(Dispatcher, "start_polling", polling)
    monkeypatch.setattr("aiogram.Bot.set_my_commands", commands)
    config = BotConfig(
        telegram_token="123456:TEST-TOKEN", api_password="secret", redis_url=redis_url
    )

    await app.run(config)

    polling.assert_awaited_once()
    commands.assert_awaited_once()
    assert commands.await_args is not None
    assert len(commands.await_args.args[0]) == len(texts.COMMAND_DESCRIPTIONS)


def test_main_runs_bot_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[Coroutine[Any, Any, None]] = []

    def fake_run(coroutine: Coroutine[Any, Any, None]) -> None:
        started.append(coroutine)
        coroutine.close()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
    monkeypatch.setenv("BOT_API_PASSWORD", "secret")
    monkeypatch.setattr("bot.app.asyncio.run", fake_run)
    monkeypatch.setattr("bot.app.logging.basicConfig", MagicMock())

    app.main()

    assert len(started) == 1
    assert asyncio.iscoroutine(started[0])


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    main = MagicMock()
    monkeypatch.setattr("bot.app.main", main)

    runpy.run_module("bot", run_name="__main__")

    main.assert_called_once_with()


def test_main_exits_with_a_clear_message_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bot.app.ENV_FILE", Path("/nonexistent/.env"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("BOT_API_PASSWORD", "secret")

    with pytest.raises(SystemExit, match="Missing environment variables: TELEGRAM_BOT_TOKEN"):
        app.main()
