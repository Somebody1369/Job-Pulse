from dataclasses import asdict
from typing import Final

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.api import BotApi
from bot.formatting import subscription_summary
from bot.handlers.helpers import chat_id_of, edit, edit_markup, username_of
from bot.keyboards import (
    ANY_VALUE,
    FormStep,
    SkillToggle,
    SubscriptionAction,
    experience_keyboard,
    remote_keyboard,
    salary_keyboard,
    skills_keyboard,
    subscription_keyboard,
)
from bot.models import Skill, SubscriptionDraft
from bot.states import SubscribeForm

SKILL_OPTIONS: Final = 24


async def subscribe(message: Message, state: FSMContext, api: BotApi) -> None:
    skills = await api.skills(limit=SKILL_OPTIONS)
    await state.set_state(SubscribeForm.skills)
    await state.set_data({"options": [asdict(skill) for skill in skills], "selected": []})
    await message.answer(texts.CHOOSE_SKILLS, reply_markup=skills_keyboard(skills, ()))


async def toggle_skill(
    callback: CallbackQuery, callback_data: SkillToggle, state: FSMContext
) -> None:
    data = await state.get_data()
    selected = sorted(set(data["selected"]) ^ {callback_data.slug})
    await state.update_data(selected=selected)
    options = [Skill(**option) for option in data["options"]]
    await edit_markup(callback, skills_keyboard(options, selected))


async def finish_skills(
    callback: CallbackQuery, callback_data: FormStep, state: FSMContext
) -> None:
    if callback_data.value == "cancel":
        await state.clear()
        await edit(callback, texts.SUBSCRIPTION_CANCELLED)
        return
    if not (await state.get_data())["selected"]:
        await callback.answer(texts.SKILLS_REQUIRED, show_alert=True)
        return
    await state.set_state(SubscribeForm.remote)
    await edit(callback, texts.CHOOSE_REMOTE, reply_markup=remote_keyboard())


async def choose_remote(
    callback: CallbackQuery, callback_data: FormStep, state: FSMContext
) -> None:
    await state.update_data(remote_only=callback_data.value == "yes")
    await state.set_state(SubscribeForm.salary)
    await edit(callback, texts.CHOOSE_SALARY, reply_markup=salary_keyboard())


async def choose_salary(
    callback: CallbackQuery, callback_data: FormStep, state: FSMContext
) -> None:
    await state.update_data(min_salary_usd=_optional_number(callback_data.value))
    await state.set_state(SubscribeForm.experience)
    await edit(callback, texts.CHOOSE_EXPERIENCE, reply_markup=experience_keyboard())


async def choose_experience(
    callback: CallbackQuery, callback_data: FormStep, state: FSMContext, api: BotApi
) -> None:
    data = await state.get_data()
    await state.clear()
    chat_id = chat_id_of(callback)
    await api.register(chat_id, username_of(callback.from_user))
    subscription = await api.create_subscription(
        chat_id,
        SubscriptionDraft(
            skills=tuple(data["selected"]),
            remote_only=data["remote_only"],
            min_salary_usd=data["min_salary_usd"],
            max_experience_years=_optional_number(callback_data.value),
        ),
    )
    await edit(callback, f"{texts.SUBSCRIPTION_CREATED}\n{subscription_summary(subscription)}")


async def list_subscriptions(message: Message, api: BotApi) -> None:
    subscriptions = await api.subscriptions(message.chat.id)
    if not subscriptions:
        await message.answer(texts.NO_SUBSCRIPTIONS)
        return
    for subscription in subscriptions:
        await message.answer(
            subscription_summary(subscription), reply_markup=subscription_keyboard(subscription)
        )


async def manage_subscription(
    callback: CallbackQuery, callback_data: SubscriptionAction, api: BotApi
) -> None:
    chat_id = chat_id_of(callback)
    if callback_data.action == "delete":
        await api.delete_subscription(chat_id, callback_data.id)
        await edit(callback, texts.SUBSCRIPTION_DELETED)
        return
    subscription = await api.set_subscription_active(
        chat_id, callback_data.id, active=callback_data.action == "resume"
    )
    await edit(
        callback,
        subscription_summary(subscription),
        reply_markup=subscription_keyboard(subscription),
    )


def _optional_number(value: str) -> int | None:
    return None if value == ANY_VALUE else int(value)


def create_router() -> Router:
    router = Router(name="subscriptions")
    router.message.register(subscribe, Command("subscribe"))
    router.callback_query.register(toggle_skill, SubscribeForm.skills, SkillToggle.filter())
    router.callback_query.register(
        finish_skills, SubscribeForm.skills, FormStep.filter(F.field == "skills")
    )
    router.callback_query.register(
        choose_remote, SubscribeForm.remote, FormStep.filter(F.field == "remote")
    )
    router.callback_query.register(
        choose_salary, SubscribeForm.salary, FormStep.filter(F.field == "salary")
    )
    router.callback_query.register(
        choose_experience, SubscribeForm.experience, FormStep.filter(F.field == "experience")
    )
    router.message.register(list_subscriptions, Command("subscriptions"))
    router.callback_query.register(manage_subscription, SubscriptionAction.filter())
    return router
