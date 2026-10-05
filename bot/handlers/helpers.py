from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User


def chat_id_of(callback: CallbackQuery) -> int:
    return callback.message.chat.id if callback.message else callback.from_user.id


def username_of(user: User | None) -> str:
    return (user.username or "") if user else ""


async def edit(
    callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def edit_markup(callback: CallbackQuery, reply_markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=reply_markup)
    await callback.answer()
