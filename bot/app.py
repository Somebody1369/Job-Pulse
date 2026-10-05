import asyncio
import logging
from functools import partial
from pathlib import Path
from zoneinfo import ZoneInfo

import environ
import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, ErrorEvent

from bot import texts
from bot.api import ApiError, BotApi, JobPulseApi
from bot.config import BotConfig, ConfigError
from bot.handlers import common, market, subscriptions
from bot.notifier import broadcast_weekly_report, deliver_notifications
from bot.scheduling import run_every, run_weekly

logger = logging.getLogger(__name__)

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


async def handle_api_error(event: ErrorEvent) -> bool:
    logger.error("JobPulse API request failed: %s", event.exception)
    if event.update.message:
        await event.update.message.answer(texts.SERVICE_UNAVAILABLE)
    elif event.update.callback_query:
        await event.update.callback_query.answer(texts.SERVICE_UNAVAILABLE, show_alert=True)
    return True


def build_dispatcher(api: BotApi, storage: BaseStorage) -> Dispatcher:
    dispatcher = Dispatcher(storage=storage, api=api)
    dispatcher.include_routers(
        common.create_router(), subscriptions.create_router(), market.create_router()
    )
    dispatcher.errors.register(handle_api_error, ExceptionTypeFilter(ApiError, httpx.HTTPError))
    return dispatcher


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command=command, description=description)
        for command, description in texts.COMMAND_DESCRIPTIONS
    ]


async def run(config: BotConfig) -> None:
    api = JobPulseApi(config.api_url, username=config.api_username, password=config.api_password)
    bot = Bot(
        config.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    storage = RedisStorage.from_url(config.redis_url) if config.redis_url else MemoryStorage()
    dispatcher = build_dispatcher(api, storage)
    background = [
        asyncio.create_task(
            run_every(
                "notifications",
                config.notify_interval,
                partial(
                    deliver_notifications,
                    bot,
                    api,
                    limit=config.notifications_per_subscription,
                ),
            )
        ),
        asyncio.create_task(
            run_weekly(
                "weekly report",
                weekday=config.weekly_report_weekday,
                hour=config.weekly_report_hour,
                zone=ZoneInfo(config.timezone),
                job=partial(broadcast_weekly_report, bot, api),
            )
        ),
    ]
    try:
        await bot.set_my_commands(bot_commands())
        await dispatcher.start_polling(bot)
    finally:
        for task in background:
            task.cancel()
        await api.close()
        await storage.close()
        await bot.session.close()


def main() -> None:
    environ.Env.read_env(ENV_FILE)
    try:
        config = BotConfig.from_env()
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(run(config))
