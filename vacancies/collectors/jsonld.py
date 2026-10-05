import json
from collections.abc import Iterator
from typing import Any, Final

from bs4 import BeautifulSoup

from vacancies.collectors.base import VacancyDetails
from vacancies.salary import NO_SALARY, SalaryRange

JOB_POSTING_TYPE: Final = "JobPosting"
REMOTE_LOCATION_TYPE: Final = "TELECOMMUTE"
MONTHLY_UNIT: Final = "MONTH"


def find_job_posting(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.get_text())
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(payload):
            if node.get("@type") == JOB_POSTING_TYPE:
                return node
    return None


def details_from_job_posting(posting: dict[str, Any]) -> VacancyDetails:
    organization = _as_dict(posting.get("hiringOrganization"))
    return VacancyDetails(
        company=_as_str(organization.get("name")),
        company_website=_as_str(organization.get("sameAs")),
        locations=_locations(posting.get("jobLocation")),
        is_remote=posting.get("jobLocationType") == REMOTE_LOCATION_TYPE,
        salary=_base_salary(posting.get("baseSalary")) or NO_SALARY,
        experience_months=_as_int(
            _as_dict(posting.get("experienceRequirements")).get("monthsOfExperience")
        ),
    )


def _iter_nodes(payload: Any) -> Iterator[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_nodes(item)
    elif isinstance(payload, dict):
        yield payload
        yield from _iter_nodes(payload.get("@graph", []))


def _locations(job_location: Any) -> tuple[str, ...]:
    places = job_location if isinstance(job_location, list) else [job_location]
    localities: list[str] = []
    for place in places:
        address = _as_dict(_as_dict(place).get("address"))
        locality = address.get("addressLocality")
        names = locality if isinstance(locality, list) else [locality]
        localities.extend(name for name in map(_as_str, names) if name)
        if not any(names) and (country := _as_str(address.get("addressCountry"))):
            localities.append(country)
    return tuple(dict.fromkeys(localities))


def _base_salary(salary: Any) -> SalaryRange | None:
    salary = _as_dict(salary)
    currency = _as_str(salary.get("currency")).upper()
    value = salary.get("value")
    if isinstance(value, dict):
        if value.get("unitText", MONTHLY_UNIT) != MONTHLY_UNIT:
            return None
        exact = _as_int(value.get("value"))
        minimum = _as_int(value.get("minValue"), default=exact)
        maximum = _as_int(value.get("maxValue"), default=exact)
    else:
        minimum = maximum = _as_int(value)
    if not currency or (minimum is None and maximum is None):
        return None
    return SalaryRange(minimum=minimum, maximum=maximum, currency=currency)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_int(value: Any, default: int | None = None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return int(value)
