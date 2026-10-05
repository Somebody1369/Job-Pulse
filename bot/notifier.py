import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BufferedInputFile

from bot import texts
from bot.api import BotApi
from bot.formatting import vacancy_card
from bot.keyboards import open_vacancy_keyboard

logger = logging.getLogger(__name__)


async def deliver_notifications(bot: Bot, api: BotApi, *, limit: int) -> int:
    delivered: list[tuple[int, int]] = []
    blocked: set[int] = set()
    sent = 0
    for notification in await api.notifications(limit=limit):
        if notification.chat_id in blocked:
            continue
        vacancy = notification.vacancy
        try:
            await bot.send_message(
                notification.chat_id,
                vacancy_card(vacancy),
                reply_markup=open_vacancy_keyboard(vacancy.url),
            )
        except TelegramForbiddenError:
            blocked.add(notification.chat_id)
            continue
        except TelegramBadRequest as exc:
            logger.warning("Skipping vacancy %s for %s: %s", vacancy.id, notification.chat_id, exc)
        else:
            sent += 1
        delivered.append((notification.subscription_id, vacancy.id))
    await api.acknowledge(delivered)
    for chat_id in blocked:
        await api.forget(chat_id)
    return sent


async def broadcast_weekly_report(bot: Bot, api: BotApi) -> int:
    image = await api.latest_report()
    if image is None:
        return 0
    sent = 0
    for chat_id in await api.weekly_report_subscribers():
        try:
            await bot.send_photo(
                chat_id,
                BufferedInputFile(image, filename="jobpulse-weekly.png"),
                caption=texts.REPORT_CAPTION,
            )
        except TelegramForbiddenError:
            await api.forget(chat_id)
            continue
        sent += 1
    return sent
