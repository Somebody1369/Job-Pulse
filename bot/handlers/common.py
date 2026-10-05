from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.api import BotApi
from bot.handlers.helpers import chat_id_of, edit, username_of
from bot.keyboards import ForgetAction, forget_keyboard


async def start(message: Message, api: BotApi) -> None:
    await api.register(message.chat.id, username_of(message.from_user))
    await message.answer(texts.WELCOME)


async def show_help(message: Message) -> None:
    await message.answer(texts.WELCOME)


async def forget(message: Message) -> None:
    await message.answer(texts.FORGET_CONFIRM, reply_markup=forget_keyboard())


async def confirm_forget(
    callback: CallbackQuery, callback_data: ForgetAction, api: BotApi, state: FSMContext
) -> None:
    if not callback_data.confirmed:
        await edit(callback, texts.SUBSCRIPTION_CANCELLED)
        return
    await state.clear()
    await api.forget(chat_id_of(callback))
    await edit(callback, texts.FORGOTTEN)


def create_router() -> Router:
    router = Router(name="common")
    router.message.register(start, CommandStart())
    router.message.register(show_help, Command("help"))
    router.message.register(forget, Command("forget"))
    router.callback_query.register(confirm_forget, ForgetAction.filter())
    return router
