from typing import Final

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from bot import texts
from bot.api import BotApi
from bot.formatting import market_summary, salary_table, vacancy_card
from bot.handlers.helpers import username_of
from bot.keyboards import open_vacancy_keyboard
from bot.models import MarketSnapshot

SEARCH_LIMIT: Final = 5
TOP_COMPETITION: Final = 3


async def search(message: Message, command: CommandObject, api: BotApi) -> None:
    if not command.args:
        await message.answer(texts.SEARCH_USAGE)
        return
    vacancies = await api.search(command.args, limit=SEARCH_LIMIT)
    if not vacancies:
        await message.answer(texts.NOTHING_FOUND)
        return
    for vacancy in vacancies:
        await message.answer(vacancy_card(vacancy), reply_markup=open_vacancy_keyboard(vacancy.url))


async def market(message: Message, command: CommandObject, api: BotApi) -> None:
    snapshots = await api.market_overview()
    if not snapshots:
        await message.answer(texts.MARKET_EMPTY)
        return
    query = (command.args or "").strip().casefold()
    selected = _find_category(snapshots, query) if query else _headline(snapshots)
    if not selected:
        categories = ", ".join(snapshot.category for snapshot in snapshots if snapshot.category)
        await message.answer(texts.MARKET_UNKNOWN.format(categories=categories))
        return
    await message.answer("\n\n".join(market_summary(snapshot) for snapshot in selected))


async def salary(message: Message, command: CommandObject, api: BotApi) -> None:
    language, _, years_text = (command.args or "").strip().partition(" ")
    if not language:
        await message.answer(texts.SALARY_USAGE)
        return
    years = _parse_years(years_text)
    rows = await api.salaries(language, group="experience" if years is not None else "seniority")
    if not rows:
        await message.answer(texts.SALARY_EMPTY.format(language=language))
        return
    await message.answer(salary_table(language, rows, years=years))


async def report(message: Message, api: BotApi) -> None:
    image = await api.latest_report()
    if image is None:
        await message.answer(texts.REPORT_EMPTY)
        return
    await message.answer_photo(
        BufferedInputFile(image, filename="jobpulse-report.png"), caption=texts.REPORT_CAPTION
    )


async def weekly(message: Message, api: BotApi) -> None:
    await api.register(message.chat.id, username_of(message.from_user))
    enabled = not await api.weekly_report_enabled(message.chat.id)
    await api.set_weekly_report(message.chat.id, enabled=enabled)
    await message.answer(texts.WEEKLY_ON if enabled else texts.WEEKLY_OFF)


def _find_category(snapshots: list[MarketSnapshot], query: str) -> list[MarketSnapshot]:
    for snapshot in snapshots:
        names = (snapshot.category.casefold(), snapshot.label.casefold())
        if query in names or snapshot.label.casefold().startswith(query):
            return [snapshot]
    return []


def _headline(snapshots: list[MarketSnapshot]) -> list[MarketSnapshot]:
    overall = [snapshot for snapshot in snapshots if not snapshot.category]
    categories = sorted(
        (snapshot for snapshot in snapshots if snapshot.category),
        key=lambda snapshot: snapshot.candidates_per_vacancy or 0,
        reverse=True,
    )
    return overall + categories[:TOP_COMPETITION]


def _parse_years(text: str) -> float | None:
    try:
        return float(text.replace(",", ".")) if text else None
    except ValueError:
        return None


def create_router() -> Router:
    router = Router(name="market")
    router.message.register(search, Command("search"))
    router.message.register(market, Command("market"))
    router.message.register(salary, Command("salary"))
    router.message.register(report, Command("report"))
    router.message.register(weekly, Command("weekly"))
    return router
