from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from django.db.models import Case, Count, IntegerField, Q, QuerySet, Value, When

from core.aggregates import Median, Percentile
from market.models import MarketSnapshot, SalaryResponse, SalarySurvey
from vacancies.models import Skill

MIN_RESPONSES: Final = 20
NO_SENIORITY: Final = ("", "Немає тайтлу")
EXPERIENCE_BUCKETS: Final = (
    ("< 1", Decimal(0), Decimal(1)),
    ("1–2", Decimal(1), Decimal(2)),
    ("2–3", Decimal(2), Decimal(3)),
    ("3–5", Decimal(3), Decimal(5)),
    ("5–7", Decimal(5), Decimal(7)),
    ("7–10", Decimal(7), Decimal(10)),
    ("10+", Decimal(10), None),
)


@dataclass(frozen=True, slots=True)
class MarketRow:
    category: str
    label: str
    calculated_on: date
    candidates: int
    vacancies: int
    vacancies_change: int | None
    candidates_per_vacancy: float | None
    expected_min: int
    expected_max: int
    offered_min: int
    offered_max: int
    applications_per_vacancy: Decimal


@dataclass(frozen=True, slots=True)
class TrendPoint:
    day: date
    candidates: int
    vacancies: int


@dataclass(frozen=True, slots=True)
class SkillDemandRow:
    skill: str
    current: int
    previous: int

    @property
    def change(self) -> int:
        return self.current - self.previous


@dataclass(frozen=True, slots=True)
class SalaryRow:
    group: str
    responses: int
    p25: int
    median: int
    p75: int


@dataclass(frozen=True, slots=True)
class SalaryPoint:
    period: date
    responses: int
    median: int


def market_overview() -> list[MarketRow]:
    latest = MarketSnapshot.objects.order_by("category", "-calculated_on").distinct("category")
    rows = [
        MarketRow(
            category=snapshot.category,
            label=snapshot.category_label,
            calculated_on=snapshot.calculated_on,
            candidates=snapshot.active_candidates,
            vacancies=snapshot.vacancies_online,
            vacancies_change=snapshot.vacancies_change,
            candidates_per_vacancy=snapshot.candidates_per_vacancy,
            expected_min=snapshot.expected_min,
            expected_max=snapshot.expected_max,
            offered_min=snapshot.offered_min,
            offered_max=snapshot.offered_max,
            applications_per_vacancy=snapshot.applications_per_vacancy,
        )
        for snapshot in latest
    ]
    return sorted(rows, key=lambda row: (row.category != "", -(row.candidates_per_vacancy or 0)))


def market_trend(category: str, *, days: int, today: date) -> list[TrendPoint]:
    snapshots = MarketSnapshot.objects.filter(
        category=category, calculated_on__gt=today - timedelta(days=days)
    ).order_by("calculated_on")
    return [
        TrendPoint(
            day=snapshot.calculated_on,
            candidates=snapshot.active_candidates,
            vacancies=snapshot.vacancies_online,
        )
        for snapshot in snapshots
    ]


def skill_demand(*, now: datetime, days: int, limit: int) -> list[SkillDemandRow]:
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    current = Q(vacancies__published_at__gte=current_start, vacancies__published_at__lt=now)
    previous = Q(
        vacancies__published_at__gte=previous_start,
        vacancies__published_at__lt=current_start,
    )
    skills = (
        Skill.objects.annotate(
            current=Count("vacancies__fingerprint", filter=current, distinct=True),
            previous=Count("vacancies__fingerprint", filter=previous, distinct=True),
        )
        .filter(Q(current__gt=0) | Q(previous__gt=0))
        .order_by("-current", "-previous", "name")[:limit]
    )
    return [
        SkillDemandRow(skill=skill.name, current=skill.current, previous=skill.previous)
        for skill in skills
    ]


def market_categories() -> list[tuple[str, str]]:
    latest = MarketSnapshot.objects.order_by("category", "-calculated_on").distinct("category")
    return sorted(
        latest.values_list("category", "category_label"), key=lambda pair: pair[1].casefold()
    )


def latest_survey() -> SalarySurvey | None:
    return SalarySurvey.objects.order_by("-period").first()


def survey_languages(survey: SalarySurvey) -> list[str]:
    return list(
        survey.responses.exclude(programming_language="")
        .values("programming_language")
        .annotate(responses=Count("id"))
        .filter(responses__gte=MIN_RESPONSES)
        .order_by("-responses")
        .values_list("programming_language", flat=True)
    )


def salary_by_seniority(survey: SalarySurvey, language: str) -> list[SalaryRow]:
    responses = _salaries(survey, language).exclude(seniority__in=NO_SENIORITY)
    return [
        _salary_row(row["seniority"], row)
        for row in _salary_groups(responses, group="seniority", order="median")
    ]


def salary_by_experience(survey: SalarySurvey, language: str) -> list[SalaryRow]:
    bucket = Case(
        *(
            When(_experience_range(low, high), then=Value(position))
            for position, (_, low, high) in enumerate(EXPERIENCE_BUCKETS)
        ),
        output_field=IntegerField(),
    )
    responses = _salaries(survey, language).annotate(bucket=bucket).exclude(bucket=None)
    return [
        _salary_row(EXPERIENCE_BUCKETS[row["bucket"]][0], row)
        for row in _salary_groups(responses, group="bucket", order="bucket")
    ]


def salary_dynamics(language: str) -> list[SalaryPoint]:
    rows = (
        SalaryResponse.objects.filter(programming_language__iexact=language)
        .values("survey__period")
        .annotate(responses=Count("id"), median=Median("salary_usd"))
        .filter(responses__gte=MIN_RESPONSES)
        .order_by("survey__period")
    )
    return [
        SalaryPoint(
            period=row["survey__period"], responses=row["responses"], median=round(row["median"])
        )
        for row in rows
    ]


def _salaries(survey: SalarySurvey, language: str) -> QuerySet[SalaryResponse]:
    return SalaryResponse.objects.filter(survey=survey, programming_language__iexact=language)


def _salary_groups(
    responses: QuerySet[SalaryResponse], *, group: str, order: str
) -> list[dict[str, Any]]:
    return list(
        responses.values(group)
        .annotate(
            responses=Count("id"),
            p25=Percentile("salary_usd", 0.25),
            median=Median("salary_usd"),
            p75=Percentile("salary_usd", 0.75),
        )
        .filter(responses__gte=MIN_RESPONSES)
        .order_by(order)
    )


def _salary_row(group: str, row: dict[str, Any]) -> SalaryRow:
    return SalaryRow(
        group=group,
        responses=row["responses"],
        p25=round(row["p25"]),
        median=round(row["median"]),
        p75=round(row["p75"]),
    )


def _experience_range(low: Decimal, high: Decimal | None) -> Q:
    condition = Q(experience_years__gte=low)
    return condition if high is None else condition & Q(experience_years__lt=high)
