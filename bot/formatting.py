import math
from html import escape
from typing import Final

from bot import texts
from bot.models import MarketSnapshot, SalaryRow, Subscription, Vacancy

MAX_SKILLS: Final = 8
HIGHLIGHT: Final = "→ "


def vacancy_card(vacancy: Vacancy) -> str:
    place = texts.REMOTE if vacancy.is_remote else ", ".join(vacancy.locations) or texts.OFFICE
    details = " · ".join(
        part
        for part in (
            escape(vacancy.company),
            vacancy.board.upper(),
            escape(vacancy.salary_text) or texts.SALARY_NOT_SPECIFIED,
            escape(place),
        )
        if part
    )
    skills = ", ".join(escape(skill) for skill in vacancy.skills[:MAX_SKILLS])
    lines = [f"<b>{escape(vacancy.title)}</b>", details]
    if skills:
        lines.append(f"<i>{skills}</i>")
    return "\n".join(lines)


def market_summary(snapshot: MarketSnapshot) -> str:
    change = "" if snapshot.vacancies_change is None else f" ({snapshot.vacancies_change:+d})"
    competition = (
        f"{snapshot.candidates_per_vacancy:g} {texts.CANDIDATES_PER_VACANCY}"
        if snapshot.candidates_per_vacancy is not None
        else "—"
    )
    low_expected, high_expected = snapshot.expected
    low_offered, high_offered = snapshot.offered
    return "\n".join(
        (
            f"<b>{escape(snapshot.label)}</b>",
            texts.MARKET_COUNTS.format(
                candidates=snapshot.candidates, vacancies=snapshot.vacancies, change=change
            ),
            texts.MARKET_COMPETITION.format(competition=competition),
            texts.MARKET_EXPECTED.format(low=low_expected, high=high_expected),
            texts.MARKET_OFFERED.format(low=low_offered, high=high_offered),
        )
    )


def salary_table(language: str, rows: list[SalaryRow], *, years: float | None = None) -> str:
    low, median, high = texts.SALARY_LABELS
    lines = [
        texts.SALARY_HEADER.format(language=escape(language), low=low, median=median, high=high)
    ]
    for row in rows:
        marker = HIGHLIGHT if years is not None and _covers(row.group, years) else ""
        lines.append(
            f"{marker}{escape(row.group)}: {row.p25} / <b>{row.median}</b> / {row.p75} "
            f"<i>{texts.SALARY_RESPONSES.format(responses=row.responses)}</i>"
        )
    return "\n".join(lines)


def experience_bounds(label: str) -> tuple[float, float] | None:
    if label.startswith("<"):
        return 0.0, float(label.lstrip("< "))
    if label.endswith("+"):
        return float(label.rstrip("+")), math.inf
    lower, separator, upper = label.partition("–")
    if not separator:
        return None
    return float(lower), float(upper)


def subscription_summary(subscription: Subscription) -> str:
    status = texts.SUBSCRIPTION_ACTIVE if subscription.is_active else texts.SUBSCRIPTION_PAUSED
    conditions = [", ".join(escape(skill) for skill in subscription.skills)]
    if subscription.remote_only:
        conditions.append(texts.REMOTE)
    if subscription.min_salary_usd is not None:
        conditions.append(texts.FROM_SALARY.format(amount=subscription.min_salary_usd))
    if subscription.max_experience_years is not None:
        conditions.append(texts.UP_TO_YEARS.format(years=subscription.max_experience_years))
    return f"<b>#{subscription.id}</b> · {status}\n" + " · ".join(conditions)


def _covers(label: str, years: float) -> bool:
    bounds = experience_bounds(label)
    return bounds is not None and bounds[0] <= years < bounds[1]
