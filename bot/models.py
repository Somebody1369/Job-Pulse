from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    slug: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(name=data["name"], slug=data["slug"])


@dataclass(frozen=True, slots=True)
class Vacancy:
    id: int
    title: str
    url: str
    board: str
    company: str
    locations: tuple[str, ...]
    is_remote: bool | None
    salary_text: str
    skills: tuple[str, ...]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        company = data.get("company") or {}
        return cls(
            id=data["id"],
            title=data["title"],
            url=data["url"],
            board=data["board"],
            company=company.get("name", ""),
            locations=tuple(data.get("locations") or ()),
            is_remote=data.get("is_remote"),
            salary_text=data["salary"]["text"],
            skills=tuple(data.get("skills") or ()),
        )


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    category: str
    label: str
    candidates: int
    vacancies: int
    vacancies_change: int | None
    candidates_per_vacancy: float | None
    expected: tuple[int, int]
    offered: tuple[int, int]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            category=data["category"],
            label=data["category_label"],
            candidates=data["active_candidates"],
            vacancies=data["vacancies_online"],
            vacancies_change=data["vacancies_change"],
            candidates_per_vacancy=data["candidates_per_vacancy"],
            expected=(data["expected_min"], data["expected_max"]),
            offered=(data["offered_min"], data["offered_max"]),
        )


@dataclass(frozen=True, slots=True)
class SalaryRow:
    group: str
    responses: int
    p25: int
    median: int
    p75: int

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            group=data["group"],
            responses=data["responses"],
            p25=data["p25"],
            median=data["median"],
            p75=data["p75"],
        )


@dataclass(frozen=True, slots=True)
class Subscription:
    id: int
    skills: tuple[str, ...]
    remote_only: bool
    min_salary_usd: int | None
    max_experience_years: int | None
    is_active: bool

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            skills=tuple(data["skills"]),
            remote_only=data["remote_only"],
            min_salary_usd=data["min_salary_usd"],
            max_experience_years=data["max_experience_years"],
            is_active=data["is_active"],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SubscriptionDraft:
    skills: tuple[str, ...]
    remote_only: bool = False
    min_salary_usd: int | None = None
    max_experience_years: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "skills": list(self.skills),
            "remote_only": self.remote_only,
            "min_salary_usd": self.min_salary_usd,
            "max_experience_years": self.max_experience_years,
        }


@dataclass(frozen=True, slots=True)
class Notification:
    subscription_id: int
    chat_id: int
    vacancy: Vacancy

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            subscription_id=data["subscription"],
            chat_id=data["chat_id"],
            vacancy=Vacancy.from_json(data["vacancy"]),
        )
