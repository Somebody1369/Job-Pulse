from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from typing import Any, Final

from analytics.queries import (
    MarketRow,
    SalaryPoint,
    SalaryRow,
    SkillDemandRow,
    TrendPoint,
    market_overview,
    market_trend,
    salary_by_experience,
    salary_by_seniority,
    salary_dynamics,
    skill_demand,
)
from market.models import SalarySurvey
from vacancies.salary import format_salary_range

TREND_DAYS: Final = 90
SKILL_LIMIT: Final = 20
PERIOD_CHOICES: Final = (7, 30)
DEFAULT_LANGUAGE: Final = "Python"
DEFAULT_CATEGORY: Final = "python"

type Cell = str | int | float | Decimal | date | None


@dataclass(frozen=True, slots=True)
class Filters:
    language: str = DEFAULT_LANGUAGE
    category: str = DEFAULT_CATEGORY
    days: int = PERIOD_CHOICES[0]


@dataclass(frozen=True, slots=True)
class Table:
    name: str
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


class Dashboard:
    def __init__(self, filters: Filters, *, survey: SalarySurvey | None, now: datetime) -> None:
        self.filters = filters
        self.survey = survey
        self._now = now
        self._tables: dict[str, Callable[[], Table]] = {
            "market": self._market_table,
            "skills": self._skills_table,
            "seniority": self._seniority_table,
            "experience": self._experience_table,
            "dynamics": self._dynamics_table,
        }

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._tables)

    def table(self, name: str) -> Table:
        return self._tables[name]()

    @cached_property
    def overview(self) -> list[MarketRow]:
        return market_overview()

    @cached_property
    def trend(self) -> list[TrendPoint]:
        return market_trend(self.filters.category, days=TREND_DAYS, today=self._now.date())

    @cached_property
    def skills(self) -> list[SkillDemandRow]:
        return skill_demand(now=self._now, days=self.filters.days, limit=SKILL_LIMIT)

    @cached_property
    def seniority(self) -> list[SalaryRow]:
        return salary_by_seniority(self.survey, self.filters.language) if self.survey else []

    @cached_property
    def experience(self) -> list[SalaryRow]:
        return salary_by_experience(self.survey, self.filters.language) if self.survey else []

    @cached_property
    def dynamics(self) -> list[SalaryPoint]:
        return salary_dynamics(self.filters.language)

    def charts(self) -> dict[str, Any]:
        competition = [row for row in self.overview if row.category and row.candidates_per_vacancy]
        return {
            "competition": {
                "labels": [row.label for row in competition],
                "values": [row.candidates_per_vacancy for row in competition],
            },
            "trend": {
                "labels": [point.day.isoformat() for point in self.trend],
                "candidates": [point.candidates for point in self.trend],
                "vacancies": [point.vacancies for point in self.trend],
            },
            "skills": {
                "labels": [row.skill for row in self.skills],
                "current": [row.current for row in self.skills],
                "previous": [row.previous for row in self.skills],
            },
            "experience": {
                "labels": [row.group for row in self.experience],
                "p25": [row.p25 for row in self.experience],
                "median": [row.median for row in self.experience],
                "p75": [row.p75 for row in self.experience],
            },
            "dynamics": {
                "labels": [point.period.strftime("%b %Y") for point in self.dynamics],
                "median": [point.median for point in self.dynamics],
            },
        }

    def _market_table(self) -> Table:
        return Table(
            name="market",
            title="Djinni market by category",
            headers=(
                "Category",
                "Candidates",
                "Vacancies",
                "30-day change",
                "Candidates per vacancy",
                "Expected, USD",
                "Offered, USD",
                "Applications per vacancy",
                "Date",
            ),
            rows=tuple(
                (
                    row.label,
                    row.candidates,
                    row.vacancies,
                    row.vacancies_change,
                    row.candidates_per_vacancy,
                    format_salary_range(row.expected_min, row.expected_max),
                    format_salary_range(row.offered_min, row.offered_max),
                    row.applications_per_vacancy,
                    row.calculated_on,
                )
                for row in self.overview
            ),
        )

    def _skills_table(self) -> Table:
        days = self.filters.days
        return Table(
            name="skills",
            title=f"Most requested skills, last {days} days",
            headers=("Skill", f"Last {days} days", f"Previous {days} days", "Change"),
            rows=tuple((row.skill, row.current, row.previous, row.change) for row in self.skills),
        )

    def _seniority_table(self) -> Table:
        return self._salary_table(
            "seniority",
            f"{self.filters.language} salaries by seniority",
            "Seniority",
            self.seniority,
        )

    def _experience_table(self) -> Table:
        return self._salary_table(
            "experience",
            f"{self.filters.language} salaries by experience",
            "Experience, years",
            self.experience,
        )

    def _dynamics_table(self) -> Table:
        return Table(
            name="dynamics",
            title=f"{self.filters.language} median salary by survey",
            headers=("Survey", "Responses", "Median, USD"),
            rows=tuple(
                (point.period.strftime("%B %Y"), point.responses, point.median)
                for point in self.dynamics
            ),
        )

    def _salary_table(self, name: str, title: str, group: str, rows: list[SalaryRow]) -> Table:
        survey = f" ({self.survey.period:%B %Y})" if self.survey else ""
        return Table(
            name=name,
            title=f"{title}{survey}",
            headers=(group, "Responses", "25th percentile", "Median", "75th percentile"),
            rows=tuple((row.group, row.responses, row.p25, row.median, row.p75) for row in rows),
        )
