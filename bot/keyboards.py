from collections.abc import Collection, Sequence
from typing import Final

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from bot.models import Skill, Subscription

SKILL_COLUMNS: Final = 3
SALARY_OPTIONS: Final = (1000, 2000, 3000, 4000, 5000)
EXPERIENCE_OPTIONS: Final = (1, 3, 5)
ANY_VALUE: Final = "any"


class SkillToggle(CallbackData, prefix="skill"):
    slug: str


class FormStep(CallbackData, prefix="form"):
    field: str
    value: str


class SubscriptionAction(CallbackData, prefix="sub"):
    action: str
    id: int


class ForgetAction(CallbackData, prefix="forget"):
    confirmed: bool


def skills_keyboard(skills: Sequence[Skill], selected: Collection[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for skill in skills:
        mark = "✓ " if skill.slug in selected else ""
        builder.button(text=f"{mark}{skill.name}", callback_data=SkillToggle(slug=skill.slug))
    builder.adjust(SKILL_COLUMNS)
    builder.row(
        InlineKeyboardButton(
            text=texts.DONE, callback_data=FormStep(field="skills", value="done").pack()
        ),
        InlineKeyboardButton(
            text=texts.CANCEL, callback_data=FormStep(field="skills", value="cancel").pack()
        ),
    )
    return builder.as_markup()


def remote_keyboard() -> InlineKeyboardMarkup:
    return _choices("remote", [(texts.REMOTE_ONLY, "yes"), (texts.REMOTE_ANY, "no")], columns=2)


def salary_keyboard() -> InlineKeyboardMarkup:
    options = [(texts.ANY, ANY_VALUE), *((f"${amount}+", str(amount)) for amount in SALARY_OPTIONS)]
    return _choices("salary", options, columns=3)


def experience_keyboard() -> InlineKeyboardMarkup:
    options = [
        (texts.ANY_EXPERIENCE, ANY_VALUE),
        *((texts.UP_TO_YEARS.format(years=years), str(years)) for years in EXPERIENCE_OPTIONS),
    ]
    return _choices("experience", options, columns=2)


def subscription_keyboard(subscription: Subscription) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle = "pause" if subscription.is_active else "resume"
    builder.button(
        text=texts.PAUSE if subscription.is_active else texts.RESUME,
        callback_data=SubscriptionAction(action=toggle, id=subscription.id),
    )
    builder.button(
        text=texts.DELETE, callback_data=SubscriptionAction(action="delete", id=subscription.id)
    )
    return builder.as_markup()


def forget_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.YES, callback_data=ForgetAction(confirmed=True))
    builder.button(text=texts.NO, callback_data=ForgetAction(confirmed=False))
    return builder.as_markup()


def open_vacancy_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.OPEN, url=url)]])


def _choices(
    field: str, options: Sequence[tuple[str, str]], *, columns: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in options:
        builder.button(text=label, callback_data=FormStep(field=field, value=value))
    builder.adjust(columns)
    return builder.as_markup()
