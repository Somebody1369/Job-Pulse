from typing import Any
from unittest.mock import MagicMock

import pytest
from aiogram.filters import CommandObject
from aiogram.types import BufferedInputFile

from bot import texts
from bot.handlers import common, market, subscriptions
from bot.keyboards import ForgetAction, FormStep, SkillToggle, SubscriptionAction
from bot.models import SalaryRow, Subscription, SubscriptionDraft
from bot.states import SubscribeForm
from tests.bot_fakes import (
    CHAT_ID,
    FakeApi,
    fake_callback,
    fake_message,
    fsm_context,
    make_snapshot,
    make_vacancy,
)


def command(args: str | None) -> CommandObject:
    return CommandObject(command="test", args=args)


def answered(message: MagicMock) -> list[str]:
    return [call.args[0] for call in message.answer.await_args_list]


async def test_start_registers_subscriber() -> None:
    api = FakeApi()
    message = fake_message(username=None)

    await common.start(message, api)
    await common.show_help(message)

    assert api.calls == [("register", (CHAT_ID, ""))]
    assert answered(message) == [texts.WELCOME, texts.WELCOME]


@pytest.mark.parametrize("confirmed", [True, False])
async def test_forget_requires_confirmation(confirmed: bool) -> None:
    api = FakeApi()
    message = fake_message()
    callback = fake_callback(message)
    state = fsm_context()
    await state.set_state(SubscribeForm.skills)

    await common.forget(message)
    await common.confirm_forget(callback, ForgetAction(confirmed=confirmed), api, state)

    assert answered(message) == [texts.FORGET_CONFIRM]
    expected = texts.FORGOTTEN if confirmed else texts.SUBSCRIPTION_CANCELLED
    message.edit_text.assert_awaited_once_with(expected, reply_markup=None)
    assert (("forget", CHAT_ID) in api.calls) is confirmed
    assert (await state.get_state() is None) is confirmed


async def test_subscribe_dialog_creates_subscription() -> None:
    api = FakeApi()
    message = fake_message()
    state = fsm_context()

    await subscriptions.subscribe(message, state, api)
    for slug in ("python", "django", "python"):
        await subscriptions.toggle_skill(fake_callback(message), SkillToggle(slug=slug), state)
    await subscriptions.finish_skills(
        fake_callback(message), FormStep(field="skills", value="done"), state
    )
    await subscriptions.choose_remote(
        fake_callback(message), FormStep(field="remote", value="yes"), state
    )
    await subscriptions.choose_salary(
        fake_callback(message), FormStep(field="salary", value="3000"), state
    )
    await subscriptions.choose_experience(
        fake_callback(message), FormStep(field="experience", value="3"), state, api
    )

    assert answered(message) == [texts.CHOOSE_SKILLS]
    assert message.edit_reply_markup.await_count == 3
    assert api.calls[-1] == (
        "create_subscription",
        (
            CHAT_ID,
            SubscriptionDraft(
                skills=("django",), remote_only=True, min_salary_usd=3000, max_experience_years=3
            ),
        ),
    )
    assert await state.get_state() is None
    final_text = message.edit_text.await_args_list[-1].args[0]
    assert final_text.startswith(texts.SUBSCRIPTION_CREATED)


async def test_subscribe_dialog_with_any_options() -> None:
    api = FakeApi()
    message = fake_message()
    state = fsm_context()
    await subscriptions.subscribe(message, state, api)
    await subscriptions.toggle_skill(fake_callback(message), SkillToggle(slug="python"), state)
    await subscriptions.finish_skills(
        fake_callback(message), FormStep(field="skills", value="done"), state
    )
    await subscriptions.choose_remote(
        fake_callback(message), FormStep(field="remote", value="no"), state
    )
    await subscriptions.choose_salary(
        fake_callback(message), FormStep(field="salary", value="any"), state
    )
    await subscriptions.choose_experience(
        fake_callback(message), FormStep(field="experience", value="any"), state, api
    )

    draft = api.calls[-1][1][1]
    assert draft == SubscriptionDraft(skills=("python",))


async def test_subscribe_requires_skills_and_can_be_cancelled() -> None:
    api = FakeApi()
    message = fake_message()
    state = fsm_context()
    await subscriptions.subscribe(message, state, api)
    empty = fake_callback(message)

    await subscriptions.finish_skills(empty, FormStep(field="skills", value="done"), state)
    await subscriptions.finish_skills(
        fake_callback(message), FormStep(field="skills", value="cancel"), state
    )

    empty.answer.assert_awaited_once_with(texts.SKILLS_REQUIRED, show_alert=True)
    assert await state.get_state() is None
    message.edit_text.assert_awaited_once_with(texts.SUBSCRIPTION_CANCELLED, reply_markup=None)


async def test_list_and_manage_subscriptions() -> None:
    subscription = Subscription(9, ("go",), False, None, None, True)
    api = FakeApi(subscription_list=[subscription])
    message = fake_message()

    await subscriptions.list_subscriptions(message, api)
    await subscriptions.manage_subscription(
        fake_callback(message), SubscriptionAction(action="pause", id=9), api
    )
    await subscriptions.manage_subscription(
        fake_callback(message), SubscriptionAction(action="delete", id=9), api
    )

    assert answered(message)[0].startswith("<b>#9</b> · активна")
    assert ("set_active", (CHAT_ID, 9, False)) in api.calls
    assert ("delete_subscription", (CHAT_ID, 9)) in api.calls
    assert "на паузі" in message.edit_text.await_args_list[0].args[0]
    assert message.edit_text.await_args_list[1].args[0] == texts.SUBSCRIPTION_DELETED


async def test_list_without_subscriptions() -> None:
    message = fake_message()

    await subscriptions.list_subscriptions(message, FakeApi())

    assert answered(message) == [texts.NO_SUBSCRIPTIONS]


async def test_callbacks_without_accessible_message() -> None:
    callback = fake_callback()
    callback.message = None
    api = FakeApi(subscription_list=[Subscription(9, ("go",), False, None, None, True)])
    state = fsm_context()
    await state.set_data({"options": [], "selected": []})

    await subscriptions.manage_subscription(
        callback, SubscriptionAction(action="resume", id=9), api
    )
    await subscriptions.toggle_skill(callback, SkillToggle(slug="go"), state)

    assert ("set_active", (CHAT_ID, 9, True)) in api.calls
    assert (await state.get_data())["selected"] == ["go"]
    assert callback.answer.await_count == 2


@pytest.mark.parametrize(
    ("args", "vacancies", "expected"),
    [
        (None, [], [texts.SEARCH_USAGE]),
        ("rust", [], [texts.NOTHING_FOUND]),
    ],
)
async def test_search_feedback(args: str | None, vacancies: list[Any], expected: list[str]) -> None:
    message = fake_message()

    await market.search(message, command(args), FakeApi(vacancies=vacancies))

    assert answered(message) == expected


async def test_search_sends_vacancy_cards() -> None:
    message = fake_message()
    api = FakeApi(vacancies=[make_vacancy(), make_vacancy(id=8, title="Go Engineer")])

    await market.search(message, command("python remote"), api)

    assert ("search", "python remote") in api.calls
    assert len(answered(message)) == 2
    keyboard = message.answer.await_args_list[0].kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].url == make_vacancy().url


async def test_market_command() -> None:
    snapshots = [
        make_snapshot(category="", label="All categories", candidates_per_vacancy=6.9),
        make_snapshot(),
        make_snapshot(category="react", label="React.js", candidates_per_vacancy=107.2),
        make_snapshot(category="golang", label="Golang", candidates_per_vacancy=None),
    ]
    api = FakeApi(snapshots=snapshots)
    headline, specific, by_label, unknown, empty = (fake_message() for _ in range(5))

    await market.market(headline, command(None), api)
    await market.market(specific, command("python"), api)
    await market.market(by_label, command("react"), api)
    await market.market(unknown, command("cobol"), api)
    await market.market(empty, command(None), FakeApi())

    assert [line for line in answered(headline)[0].splitlines() if line.startswith("<b>")] == [
        "<b>All categories</b>",
        "<b>React.js</b>",
        "<b>Python</b>",
        "<b>Golang</b>",
    ]
    assert answered(specific)[0].startswith("<b>Python</b>")
    assert answered(by_label)[0].startswith("<b>React.js</b>")
    assert answered(unknown) == [texts.MARKET_UNKNOWN.format(categories="python, react, golang")]
    assert answered(empty) == [texts.MARKET_EMPTY]


async def test_salary_command() -> None:
    rows = [SalaryRow("3–5", 40, 2000, 2800, 4000)]
    api = FakeApi(salary_rows=rows)
    usage, by_seniority, by_experience, invalid_years, missing = (fake_message() for _ in range(5))

    await market.salary(usage, command(None), api)
    await market.salary(by_seniority, command("python"), api)
    await market.salary(by_experience, command("python 3,5"), api)
    await market.salary(invalid_years, command("python many"), api)
    await market.salary(missing, command("cobol"), FakeApi())

    assert answered(usage) == [texts.SALARY_USAGE]
    assert ("salaries", ("python", "seniority")) in api.calls
    assert ("salaries", ("python", "experience")) in api.calls
    assert "→ 3–5" in answered(by_experience)[0]
    assert "→" not in answered(invalid_years)[0]
    assert answered(missing) == [texts.SALARY_EMPTY.format(language="cobol")]


async def test_report_command() -> None:
    missing = fake_message()
    available = fake_message()

    await market.report(missing, FakeApi())
    await market.report(available, FakeApi(report=b"png"))

    assert answered(missing) == [texts.REPORT_EMPTY]
    photo = available.answer_photo.await_args.args[0]
    assert isinstance(photo, BufferedInputFile)
    assert available.answer_photo.await_args.kwargs["caption"] == texts.REPORT_CAPTION


async def test_weekly_command_toggles_subscription() -> None:
    api = FakeApi()
    message = fake_message()

    await market.weekly(message, api)
    await market.weekly(message, api)

    assert answered(message) == [texts.WEEKLY_ON, texts.WEEKLY_OFF]
    assert api.weekly == {CHAT_ID: False}
