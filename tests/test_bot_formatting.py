import math

import pytest

from bot import formatting
from bot.keyboards import (
    FormStep,
    SkillToggle,
    SubscriptionAction,
    experience_keyboard,
    salary_keyboard,
    skills_keyboard,
    subscription_keyboard,
)
from bot.models import SalaryRow, Skill, Subscription
from tests.bot_fakes import make_snapshot, make_vacancy


def test_vacancy_card_escapes_html_and_shows_details() -> None:
    card = formatting.vacancy_card(make_vacancy(title="QA <Lead> & Co"))

    assert card.splitlines() == [
        "<b>QA &lt;Lead&gt; &amp; Co</b>",
        "Acme · DJINNI · 4000–5000 USD · віддалено",
        "<i>Python, Django</i>",
    ]


def test_vacancy_card_for_office_vacancy_without_salary() -> None:
    card = formatting.vacancy_card(
        make_vacancy(is_remote=False, locations=("Київ", "Львів"), salary_text="", skills=())
    )

    assert card.splitlines()[1] == "Acme · DJINNI · зарплата не вказана · Київ, Львів"
    assert len(card.splitlines()) == 2
    assert "офіс" in formatting.vacancy_card(make_vacancy(is_remote=None))


def test_market_summary() -> None:
    summary = formatting.market_summary(make_snapshot())

    assert "Кандидати: 1716 · Вакансії: 120 (-17)" in summary
    assert "Конкуренція: 14.3 кандидатів на вакансію" in summary
    assert "Очікування: $1000–3800" in summary
    unknown = formatting.market_summary(
        make_snapshot(vacancies_change=None, candidates_per_vacancy=None)
    )
    assert "Вакансії: 120\n" in unknown
    assert "Конкуренція: —" in unknown


def test_salary_table_highlights_matching_experience() -> None:
    rows = [
        SalaryRow("< 1", 30, 500, 800, 1100),
        SalaryRow("3–5", 40, 2000, 2800, 4000),
        SalaryRow("10+", 25, 4000, 5500, 7000),
    ]

    table = formatting.salary_table("Python", rows, years=4)

    assert table.splitlines()[2] == "→ 3–5: 2000 / <b>2800</b> / 4000 <i>(40 відповідей)</i>"
    assert not table.splitlines()[1].startswith("→")
    assert "→" not in formatting.salary_table("Python", [SalaryRow("Middle", 9, 1, 2, 3)], years=4)


@pytest.mark.parametrize(
    ("label", "expected"),
    [("< 1", (0.0, 1.0)), ("3–5", (3.0, 5.0)), ("10+", (10.0, math.inf)), ("Senior", None)],
)
def test_experience_bounds(label: str, expected: tuple[float, float] | None) -> None:
    assert formatting.experience_bounds(label) == expected


def test_subscription_summary() -> None:
    subscription = Subscription(9, ("python", "django"), True, 3000, 3, False)

    assert formatting.subscription_summary(subscription) == (
        "<b>#9</b> · на паузі\npython, django · віддалено · від $3000 · до 3 р."
    )


def test_keyboards() -> None:
    skills = skills_keyboard([Skill("Python", "python"), Skill("Go", "go")], ["go"])
    buttons = [button for row in skills.inline_keyboard for button in row]

    assert [button.text for button in buttons] == ["Python", "✓ Go", "Готово", "Скасувати"]
    assert buttons[1].callback_data == SkillToggle(slug="go").pack()
    assert buttons[2].callback_data == FormStep(field="skills", value="done").pack()
    assert salary_keyboard().inline_keyboard[0][1].text == "$1000+"
    assert experience_keyboard().inline_keyboard[1][0].text == "до 3 р."
    paused = subscription_keyboard(Subscription(9, ("go",), False, None, None, False))
    assert (
        paused.inline_keyboard[0][0].callback_data
        == SubscriptionAction(action="resume", id=9).pack()
    )
